import os
from datetime import datetime, timedelta
from typing import Dict, List
from dotenv import load_dotenv
import requests
import json
from database import (
    init_db, User, Cycle, Issue, CycleCapacity, CycleMetrics, UserMetrics,
    BlockedPeriod, IssueStateChange, DailyMetrics
)
from sqlalchemy.orm import Session
import pandas as pd

class LinearMetricsClient:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('linear_key')
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
        }
        self.api_url = 'https://api.linear.app/graphql'
        self.db = init_db(force_recreate=True)

    def test_connection(self):
        """Test the API connection with a simple viewer query"""
        query = """
        query {
            viewer {
                id
                name
                email
            }
        }
        """
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={'query': query}
            )
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
            response.raise_for_status()
            result = response.json()
            print(f"Connected as: {result['data']['viewer']['name']}")
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False

    def _execute_query(self, query: str, variables: Dict = None) -> Dict:
        """Execute a GraphQL query against Linear API"""
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={'query': query, 'variables': variables or {}}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Error response from API: {response.text}")
            raise

    def sync_data(self):
        """Synchronize all data from Linear to local database"""
        if not self.test_connection():
            raise Exception("Failed to connect to Linear API")
        
        self.sync_users()
        self.sync_cycles()
        self.sync_issues()
        self.sync_daily_metrics()
        self.calculate_metrics()

    def sync_users(self):
        """Fetch and store team members"""
        query = """
        query {
            users(first: 100) {
                nodes {
                    id
                    name
                    email
                }
            }
        }
        """
        result = self._execute_query(query)
        users = result['data']['users']['nodes']
        
        for user_data in users:
            db_user = User(
                id=user_data['id'],
                name=user_data['name'],
                email=user_data['email']
            )
            self.db.merge(db_user)
        self.db.commit()

    def sync_cycles(self):
        """Fetch and store cycles (sprints)"""
        teams_query = """
        query {
            teams(first: 10) {
                nodes {
                    id
                    cycles(
                        first: 10,
                        last: 5,
                        orderBy: { startsAt: DESC }
                    ) {
                        nodes {
                            id
                            number
                            name
                            startsAt
                            endsAt
                            progress
                        }
                    }
                }
            }
        }
        """
        teams_result = self._execute_query(teams_query)
        teams = teams_result['data']['teams']['nodes']
        
        for team in teams:
            cycles = team['cycles']['nodes']
            for cycle_data in cycles:
                db_cycle = Cycle(
                    id=cycle_data['id'],
                    number=cycle_data['number'],
                    name=cycle_data['name'],
                    start_date=datetime.fromisoformat(cycle_data['startsAt'].replace('Z', '+00:00')),
                    end_date=datetime.fromisoformat(cycle_data['endsAt'].replace('Z', '+00:00')),
                    progress=cycle_data['progress'],
                    max_wip=5  # Default WIP limit, adjust as needed
                )
                self.db.merge(db_cycle)
        self.db.commit()

        # Then get memberships and set capacities
        for team in teams:
            members_query = """
            query($teamId: String!) {
                team(id: $teamId) {
                    memberships(first: 50) {
                        nodes {
                            user {
                                id
                            }
                        }
                    }
                }
            }
            """
            members_result = self._execute_query(members_query, {'teamId': team['id']})
            members = members_result['data']['team']['memberships']['nodes']
            
            cycles = team['cycles']['nodes']
            for cycle_data in cycles:
                for member in members:
                    capacity = CycleCapacity(
                        cycle_id=cycle_data['id'],
                        user_id=member['user']['id'],
                        capacity_hours=32.0,  # Default to 32 productive hours/week (80% of 40)
                        capacity_points=10.0  # Default story point capacity
                    )
                    self.db.merge(capacity)
            self.db.commit()

    def sync_issues(self):
        """Fetch and store issues with detailed history"""
        teams_query = """
        query {
            teams(first: 50) {
                nodes {
                    id
                }
            }
        }
        """
        teams_result = self._execute_query(teams_query)
        teams = teams_result['data']['teams']['nodes']
        
        for team in teams:
            issues_query = """
            query($teamId: String!, $after: String) {
                team(id: $teamId) {
                    issues(
                        first: 50,
                        after: $after,
                        filter: {
                            createdAt: { gte: "2024-01-01" }
                        }
                    ) {
                        nodes {
                            id
                            title
                            description
                            state {
                                name
                                type
                            }
                            priority
                            estimate
                            createdAt
                            startedAt
                            completedAt
                            cycle {
                                id
                            }
                            assignee {
                                id
                            }
                            team {
                                id
                                name
                            }
                            project {
                                id
                                name
                            }
                            labels {
                                nodes {
                                    name
                                }
                            }
                            history(first: 50) {
                                nodes {
                                    createdAt
                                    fromState {
                                        name
                                        type
                                    }
                                    toState {
                                        name
                                        type
                                    }
                                }
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
            """
            after = None
            while True:
                issues_result = self._execute_query(issues_query, {'teamId': team['id'], 'after': after})
                issues = issues_result['data']['team']['issues']['nodes']
                page_info = issues_result['data']['team']['issues']['pageInfo']
                
                for issue_data in issues:
                    # Extract initiative from labels (assuming initiative labels start with "Initiative:")
                    initiative = None
                    if 'labels' in issue_data and issue_data['labels']['nodes']:
                        for label in issue_data['labels']['nodes']:
                            if label['name'].startswith('Initiative:'):
                                initiative = label['name'].replace('Initiative:', '').strip()
                                break

                    db_issue = Issue(
                        id=issue_data['id'],
                        title=issue_data['title'],
                        description=issue_data['description'],
                        state=issue_data['state']['name'],
                        priority=issue_data['priority'],
                        estimate=issue_data['estimate'],
                        ideal_hours=0.0,  # Default since customFields are not available
                        actual_hours=0.0,  # Default since customFields are not available
                        created_at=datetime.fromisoformat(issue_data['createdAt'].replace('Z', '+00:00')),
                        started_at=datetime.fromisoformat(issue_data['startedAt'].replace('Z', '+00:00')) if issue_data['startedAt'] else None,
                        completed_at=datetime.fromisoformat(issue_data['completedAt'].replace('Z', '+00:00')) if issue_data['completedAt'] else None,
                        cycle_id=issue_data['cycle']['id'] if issue_data['cycle'] else None,
                        assignee_id=issue_data['assignee']['id'] if issue_data['assignee'] else None,
                        team_id=issue_data['team']['id'] if issue_data['team'] else None,
                        team_name=issue_data['team']['name'] if issue_data['team'] else None,
                        project_id=issue_data['project']['id'] if issue_data['project'] else None,
                        project_name=issue_data['project']['name'] if issue_data['project'] else None,
                        initiative=initiative
                    )
                    self.db.merge(db_issue)

                    # Store state changes
                    for history in issue_data['history']['nodes']:
                        if history['fromState'] and history['toState']:
                            state_change = IssueStateChange(
                                issue_id=issue_data['id'],
                                from_state=history['fromState']['name'],
                                to_state=history['toState']['name'],
                                changed_at=datetime.fromisoformat(history['createdAt'].replace('Z', '+00:00'))
                            )
                            self.db.merge(state_change)

                            # Track blocked periods
                            if history['toState']['type'] == 'blocked':
                                blocked_period = BlockedPeriod(
                                    issue_id=issue_data['id'],
                                    start_time=datetime.fromisoformat(history['createdAt'].replace('Z', '+00:00')),
                                    reason='External Dependency',  # Default reason
                                    description=f"Blocked in state: {history['toState']['name']}"
                                )
                                self.db.merge(blocked_period)
                            elif history['fromState']['type'] == 'blocked' and history['toState']['type'] != 'blocked':
                                # Find and update the open blocked period
                                blocked_period = self.db.query(BlockedPeriod).filter(
                                    BlockedPeriod.issue_id == issue_data['id'],
                                    BlockedPeriod.end_time.is_(None)
                                ).first()
                                if blocked_period:
                                    blocked_period.end_time = datetime.fromisoformat(history['createdAt'].replace('Z', '+00:00'))

                self.db.commit()
                
                if not page_info['hasNextPage']:
                    break
                    
                after = page_info['endCursor']

    def sync_daily_metrics(self):
        """Calculate and store daily metrics for active cycles"""
        cycles = self.db.query(Cycle).all()
        
        for cycle in cycles:
            current_date = cycle.start_date
            while current_date <= min(cycle.end_date, datetime.now()):
                # Calculate metrics for this day
                issues = cycle.issues
                
                # WIP count - issues in progress on this day
                wip_count = len([i for i in issues if 
                    i.started_at and i.started_at <= current_date and 
                    (not i.completed_at or i.completed_at > current_date)])
                
                # Blocked items count
                blocked_count = len([i for i in issues if any(
                    b.start_time <= current_date and (not b.end_time or b.end_time > current_date)
                    for b in i.blocked_periods)])
                
                # Completed points up to this day
                completed_points = sum(i.estimate or 0 for i in issues if 
                    i.completed_at and i.completed_at.date() <= current_date.date())
                
                # Remaining hours
                remaining_hours = sum(i.ideal_hours or 0 for i in issues if 
                    not i.completed_at or i.completed_at > current_date)
                
                daily_metrics = DailyMetrics(
                    cycle_id=cycle.id,
                    date=current_date,
                    remaining_hours=remaining_hours,
                    completed_points=completed_points,
                    wip_count=wip_count,
                    blocked_items=blocked_count
                )
                self.db.merge(daily_metrics)
                
                current_date += timedelta(days=1)
        
        self.db.commit()

    def calculate_metrics(self):
        """Calculate and store metrics for cycles and users"""
        self._calculate_cycle_metrics()
        self._calculate_user_metrics()

    def _calculate_cycle_metrics(self):
        """Calculate comprehensive metrics for each cycle"""
        cycles = self.db.query(Cycle).all()
        for cycle in cycles:
            issues = cycle.issues
            completed_issues = [i for i in issues if i.completed_at]
            
            total_points = sum(i.estimate or 0 for i in issues)
            completed_points = sum(i.estimate or 0 for i in completed_issues)
            
            # Calculate average cycle and lead times
            cycle_times = []
            lead_times = []
            blocked_times = []
            
            for issue in completed_issues:
                if issue.started_at and issue.completed_at:
                    cycle_times.append((issue.completed_at - issue.started_at).total_seconds() / 3600)
                if issue.created_at and issue.completed_at:
                    lead_times.append((issue.completed_at - issue.created_at).total_seconds() / 3600)
                
                # Calculate total blocked time
                blocked_time = sum(
                    ((b.end_time or datetime.now()) - b.start_time).total_seconds() / 3600
                    for b in issue.blocked_periods
                )
                blocked_times.append(blocked_time)
            
            # Get most common team/project/initiative info from issues
            team_counts = {}
            project_counts = {}
            initiative_counts = {}
            
            for issue in issues:
                if issue.team_name:
                    team_counts[issue.team_name] = team_counts.get(issue.team_name, 0) + 1
                if issue.project_name:
                    project_counts[issue.project_name] = project_counts.get(issue.project_name, 0) + 1
                if issue.initiative:
                    initiative_counts[issue.initiative] = initiative_counts.get(issue.initiative, 0) + 1
            
            # Get most common values
            team_name = max(team_counts.items(), key=lambda x: x[1])[0] if team_counts else None
            team_id = next((i.team_id for i in issues if i.team_name == team_name), None)
            project_name = max(project_counts.items(), key=lambda x: x[1])[0] if project_counts else None
            project_id = next((i.project_id for i in issues if i.project_name == project_name), None)
            initiative = max(initiative_counts.items(), key=lambda x: x[1])[0] if initiative_counts else None
            
            metrics = CycleMetrics(
                cycle_id=cycle.id,
                total_story_points=total_points,
                completed_story_points=completed_points,
                avg_cycle_time=sum(cycle_times) / len(cycle_times) if cycle_times else 0,
                avg_lead_time=sum(lead_times) / len(lead_times) if lead_times else 0,
                throughput=len(completed_issues),
                velocity=completed_points,
                avg_blocked_time=sum(blocked_times) / len(blocked_times) if blocked_times else 0,
                start_date=cycle.start_date,
                end_date=cycle.end_date,
                team_id=team_id,
                team_name=team_name,
                project_id=project_id,
                project_name=project_name,
                initiative=initiative
            )
            self.db.merge(metrics)
        self.db.commit()

    def _calculate_user_metrics(self):
        """Calculate comprehensive metrics for each user"""
        users = self.db.query(User).all()
        cycles = self.db.query(Cycle).all()
        
        for user in users:
            for cycle in cycles:
                user_issues = [i for i in cycle.issues if i.assignee_id == user.id]
                completed_issues = [i for i in user_issues if i.completed_at]
                
                if not completed_issues:
                    continue
                
                points_completed = sum(i.estimate or 0 for i in completed_issues)
                cycle_times = []
                
                for issue in completed_issues:
                    if issue.started_at and issue.completed_at:
                        cycle_times.append((issue.completed_at - issue.started_at).total_seconds() / 3600)
                
                # Calculate efficiency ratio (ideal vs actual hours)
                total_ideal = sum(i.ideal_hours or 0 for i in completed_issues)
                total_actual = sum(i.actual_hours or 0 for i in completed_issues)
                efficiency_ratio = total_ideal / total_actual if total_actual else 1.0
                
                # Get user capacity for this cycle
                capacity = next((c for c in cycle.capacities if c.user_id == user.id), None)
                if capacity:
                    metrics = UserMetrics(
                        user_id=user.id,
                        cycle_id=cycle.id,
                        story_points_completed=points_completed,
                        avg_cycle_time=sum(cycle_times) / len(cycle_times) if cycle_times else 0,
                        velocity=points_completed,
                        capacity_utilization=points_completed / capacity.capacity_points if capacity.capacity_points else 0,
                        efficiency_ratio=efficiency_ratio
                    )
                    self.db.merge(metrics)
        self.db.commit()

    def get_cycle_metrics_df(self) -> pd.DataFrame:
        """Return cycle metrics as a pandas DataFrame"""
        metrics = self.db.query(CycleMetrics).all()
        return pd.DataFrame([{
            'cycle_id': m.cycle_id,
            'total_story_points': m.total_story_points,
            'completed_story_points': m.completed_story_points,
            'avg_cycle_time': m.avg_cycle_time,
            'avg_lead_time': m.avg_lead_time,
            'throughput': m.throughput,
            'velocity': m.velocity,
            'avg_blocked_time': m.avg_blocked_time,
            'start_date': m.start_date,
            'end_date': m.end_date,
            'team_id': m.team_id,
            'team_name': m.team_name,
            'project_id': m.project_id,
            'project_name': m.project_name,
            'initiative': m.initiative
        } for m in metrics])

    def get_user_metrics_df(self) -> pd.DataFrame:
        """Return user metrics as a pandas DataFrame"""
        metrics = self.db.query(UserMetrics).all()
        return pd.DataFrame([{
            'user_id': m.user_id,
            'cycle_id': m.cycle_id,
            'story_points_completed': m.story_points_completed,
            'avg_cycle_time': m.avg_cycle_time,
            'velocity': m.velocity,
            'capacity_utilization': m.capacity_utilization,
            'efficiency_ratio': m.efficiency_ratio
        } for m in metrics])

    def get_daily_metrics_df(self) -> pd.DataFrame:
        """Return daily metrics as a pandas DataFrame"""
        metrics = self.db.query(DailyMetrics).all()
        return pd.DataFrame([{
            'cycle_id': m.cycle_id,
            'date': m.date,
            'remaining_hours': m.remaining_hours,
            'completed_points': m.completed_points,
            'wip_count': m.wip_count,
            'blocked_items': m.blocked_items
        } for m in metrics])

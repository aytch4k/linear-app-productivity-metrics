import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
import requests
import json
from database import init_db, User, Cycle, Issue, CycleCapacity, CycleMetrics, UserMetrics
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
        self.db = init_db()

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
            print(f"Query response: {response.text}")  # Debug output
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
        # First get teams and their cycles
        teams_query = """
        query {
            teams(first: 50) {
                nodes {
                    id
                    cycles(first: 50) {
                        nodes {
                            id
                            number
                            name
                            startsAt
                            endsAt
                        }
                    }
                }
            }
        }
        """
        teams_result = self._execute_query(teams_query)
        teams = teams_result['data']['teams']['nodes']
        
        # Store cycles first
        for team in teams:
            cycles = team['cycles']['nodes']
            for cycle_data in cycles:
                db_cycle = Cycle(
                    id=cycle_data['id'],
                    number=cycle_data['number'],
                    name=cycle_data['name'],
                    start_date=datetime.fromisoformat(cycle_data['startsAt'].replace('Z', '+00:00')),
                    end_date=datetime.fromisoformat(cycle_data['endsAt'].replace('Z', '+00:00'))
                )
                self.db.merge(db_cycle)
        self.db.commit()

        # Then get memberships for each team
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
            
            # Store cycle capacities for each member
            cycles = team['cycles']['nodes']
            for cycle_data in cycles:
                for member in members:
                    capacity = CycleCapacity(
                        cycle_id=cycle_data['id'],
                        user_id=member['user']['id'],
                        capacity=40.0  # Default to 40 hours/week, adjust as needed
                    )
                    self.db.merge(capacity)
            self.db.commit()

    def sync_issues(self):
        """Fetch and store issues (tickets)"""
        # Get teams first
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
        
        # Then get issues for each team
        for team in teams:
            issues_query = """
            query($teamId: String!) {
                team(id: $teamId) {
                    issues(first: 50) {
                        nodes {
                            id
                            title
                            description
                            state {
                                name
                            }
                            priority
                            estimate
                            createdAt
                            completedAt
                            cycle {
                                id
                            }
                            assignee {
                                id
                            }
                        }
                    }
                }
            }
            """
            issues_result = self._execute_query(issues_query, {'teamId': team['id']})
            issues = issues_result['data']['team']['issues']['nodes']
            
            for issue_data in issues:
                db_issue = Issue(
                    id=issue_data['id'],
                    title=issue_data['title'],
                    description=issue_data['description'],
                    state=issue_data['state']['name'],
                    priority=issue_data['priority'],
                    estimate=issue_data['estimate'],
                    created_at=datetime.fromisoformat(issue_data['createdAt'].replace('Z', '+00:00')),
                    completed_at=datetime.fromisoformat(issue_data['completedAt'].replace('Z', '+00:00')) if issue_data['completedAt'] else None,
                    cycle_id=issue_data['cycle']['id'] if issue_data['cycle'] else None,
                    assignee_id=issue_data['assignee']['id'] if issue_data['assignee'] else None
                )
                self.db.merge(db_issue)
            self.db.commit()

    def calculate_metrics(self):
        """Calculate and store metrics for cycles and users"""
        self._calculate_cycle_metrics()
        self._calculate_user_metrics()

    def _calculate_cycle_metrics(self):
        """Calculate metrics for each cycle"""
        cycles = self.db.query(Cycle).all()
        for cycle in cycles:
            issues = cycle.issues
            completed_issues = [i for i in issues if i.completed_at]
            
            total_points = sum(i.estimate or 0 for i in issues)
            completed_points = sum(i.estimate or 0 for i in completed_issues)
            
            if completed_issues:
                completion_times = [(i.completed_at - i.created_at).total_seconds() / 3600 
                                  for i in completed_issues]
                avg_completion_time = sum(completion_times) / len(completion_times)
            else:
                avg_completion_time = 0
            
            metrics = CycleMetrics(
                cycle_id=cycle.id,
                total_story_points=total_points,
                completed_story_points=completed_points,
                avg_completion_time=avg_completion_time,
                throughput=len(completed_issues),
                velocity=completed_points,
                start_date=cycle.start_date,
                end_date=cycle.end_date
            )
            self.db.merge(metrics)
        self.db.commit()

    def _calculate_user_metrics(self):
        """Calculate metrics for each user in each cycle"""
        users = self.db.query(User).all()
        cycles = self.db.query(Cycle).all()
        
        for user in users:
            for cycle in cycles:
                user_issues = [i for i in cycle.issues if i.assignee_id == user.id]
                completed_issues = [i for i in user_issues if i.completed_at]
                
                if not completed_issues:
                    continue
                
                points_completed = sum(i.estimate or 0 for i in completed_issues)
                completion_times = [(i.completed_at - i.created_at).total_seconds() / 3600 
                                  for i in completed_issues]
                avg_completion_time = sum(completion_times) / len(completion_times)
                
                # Get user capacity for this cycle
                capacity = next((c.capacity for c in cycle.capacities if c.user_id == user.id), 40.0)
                
                metrics = UserMetrics(
                    user_id=user.id,
                    cycle_id=cycle.id,
                    story_points_completed=points_completed,
                    avg_completion_time=avg_completion_time,
                    velocity=points_completed,
                    capacity_utilization=points_completed / capacity if capacity else 0
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
            'avg_completion_time': m.avg_completion_time,
            'throughput': m.throughput,
            'velocity': m.velocity,
            'start_date': m.start_date,
            'end_date': m.end_date
        } for m in metrics])

    def get_user_metrics_df(self) -> pd.DataFrame:
        """Return user metrics as a pandas DataFrame"""
        metrics = self.db.query(UserMetrics).all()
        return pd.DataFrame([{
            'user_id': m.user_id,
            'cycle_id': m.cycle_id,
            'story_points_completed': m.story_points_completed,
            'avg_completion_time': m.avg_completion_time,
            'velocity': m.velocity,
            'capacity_utilization': m.capacity_utilization
        } for m in metrics])

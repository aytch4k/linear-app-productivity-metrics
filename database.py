from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    issues = relationship("Issue", back_populates="assignee")
    capacity = relationship("CycleCapacity", back_populates="user")

class Cycle(Base):
    __tablename__ = 'cycles'
    
    id = Column(String, primary_key=True)
    number = Column(Integer)
    name = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    progress = Column(Float)  # Sprint progress percentage
    max_wip = Column(Integer)  # Maximum Work in Progress limit
    team_id = Column(String)  # Team ID from Linear
    team_name = Column(String)  # Team name from Linear
    issues = relationship("Issue", back_populates="cycle")
    capacities = relationship("CycleCapacity", back_populates="cycle")
    daily_metrics = relationship("DailyMetrics", back_populates="cycle")

class Issue(Base):
    __tablename__ = 'issues'
    
    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    state = Column(String)
    priority = Column(Integer)
    estimate = Column(Float)  # Story points
    ideal_hours = Column(Float)  # Estimated ideal hours for the task
    actual_hours = Column(Float)  # Actual hours spent
    created_at = Column(DateTime)
    started_at = Column(DateTime)  # When work began
    completed_at = Column(DateTime)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    assignee_id = Column(String, ForeignKey('users.id'))
    team_id = Column(String)
    team_name = Column(String)
    project_id = Column(String)
    project_name = Column(String)
    initiative = Column(String)  # Will be derived from labels
    
    cycle = relationship("Cycle", back_populates="issues")
    assignee = relationship("User", back_populates="issues")
    blocked_periods = relationship("BlockedPeriod", back_populates="issue")
    state_changes = relationship("IssueStateChange", back_populates="issue")

class BlockedPeriod(Base):
    __tablename__ = 'blocked_periods'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String, ForeignKey('issues.id'))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    reason = Column(String)  # Category/reason for being blocked
    description = Column(String)
    
    issue = relationship("Issue", back_populates="blocked_periods")

class IssueStateChange(Base):
    __tablename__ = 'issue_state_changes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String, ForeignKey('issues.id'))
    from_state = Column(String)
    to_state = Column(String)
    changed_at = Column(DateTime)
    
    issue = relationship("Issue", back_populates="state_changes")

class CycleCapacity(Base):
    __tablename__ = 'cycle_capacities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    user_id = Column(String, ForeignKey('users.id'))
    capacity_hours = Column(Float)  # Available hours
    capacity_points = Column(Float)  # Available story points
    
    cycle = relationship("Cycle", back_populates="capacities")
    user = relationship("User", back_populates="capacity")

class DailyMetrics(Base):
    __tablename__ = 'daily_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    date = Column(DateTime)
    remaining_hours = Column(Float)  # For burn down
    completed_points = Column(Float)  # For burn up
    wip_count = Column(Integer)  # Current WIP
    blocked_items = Column(Integer)  # Number of blocked items
    
    cycle = relationship("Cycle", back_populates="daily_metrics")

class CycleMetrics(Base):
    __tablename__ = 'cycle_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    total_story_points = Column(Float)
    completed_story_points = Column(Float)
    avg_cycle_time = Column(Float)  # Average time from start to completion
    avg_lead_time = Column(Float)  # Average time from creation to completion
    throughput = Column(Float)  # Completed items per cycle
    velocity = Column(Float)  # Completed story points
    avg_blocked_time = Column(Float)  # Average time items spent blocked
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    team_id = Column(String)
    team_name = Column(String)
    project_id = Column(String)
    project_name = Column(String)
    initiative = Column(String)

class UserMetrics(Base):
    __tablename__ = 'user_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.id'))
    cycle_id = Column(String, ForeignKey('cycles.id'))
    story_points_completed = Column(Float)
    avg_cycle_time = Column(Float)
    velocity = Column(Float)
    capacity_utilization = Column(Float)
    efficiency_ratio = Column(Float)  # Ratio of ideal to actual hours

class MonteCarloForecast(Base):
    __tablename__ = 'monte_carlo_forecasts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_date = Column(DateTime)
    story_points = Column(Float)
    confidence_50 = Column(Float)
    confidence_80 = Column(Float)
    confidence_95 = Column(Float)
    min_completion_date = Column(DateTime)
    max_completion_date = Column(DateTime)
    expected_completion_date = Column(DateTime)

def init_db(db_path='data/linear_metrics.db', force_recreate=False):
    # Ensure data directory exists
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    print(f"Using database at: {os.path.abspath(db_path)}")
    
    engine = create_engine(f'sqlite:///{db_path}')
    if force_recreate:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Test database connection
    try:
        session.execute(text('SELECT 1'))
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        raise
    
    return session
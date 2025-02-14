from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
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
    issues = relationship("Issue", back_populates="cycle")
    capacities = relationship("CycleCapacity", back_populates="cycle")

class Issue(Base):
    __tablename__ = 'issues'
    
    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    state = Column(String)
    priority = Column(Integer)
    estimate = Column(Float)  # Story points
    created_at = Column(DateTime)
    completed_at = Column(DateTime)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    assignee_id = Column(String, ForeignKey('users.id'))
    
    cycle = relationship("Cycle", back_populates="issues")
    assignee = relationship("User", back_populates="issues")

class CycleCapacity(Base):
    __tablename__ = 'cycle_capacities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    user_id = Column(String, ForeignKey('users.id'))
    capacity = Column(Float)  # Available hours or story points
    
    cycle = relationship("Cycle", back_populates="capacities")
    user = relationship("User", back_populates="capacity")

class CycleMetrics(Base):
    __tablename__ = 'cycle_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String, ForeignKey('cycles.id'))
    total_story_points = Column(Float)
    completed_story_points = Column(Float)
    avg_completion_time = Column(Float)
    throughput = Column(Float)
    velocity = Column(Float)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

class UserMetrics(Base):
    __tablename__ = 'user_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.id'))
    cycle_id = Column(String, ForeignKey('cycles.id'))
    story_points_completed = Column(Float)
    avg_completion_time = Column(Float)
    velocity = Column(Float)
    capacity_utilization = Column(Float)

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

def init_db(db_path='linear_metrics.db'):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
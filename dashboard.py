import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
from linear_client import LinearMetricsClient
from forecasting import MonteCarloSimulator
from database import init_db

# Initialize clients
db = init_db()
linear_client = LinearMetricsClient()
monte_carlo = MonteCarloSimulator(db)

# Page config
st.set_page_config(
    page_title="Linear.app Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Sidebar filters
st.sidebar.title("Filters")
date_range = st.sidebar.date_input(
    "Date Range",
    value=(datetime.now() - timedelta(days=90), datetime.now())
)

# Main dashboard
st.title("Linear.app Analytics Dashboard")

# Top-level metrics
col1, col2, col3, col4 = st.columns(4)

# Fetch metrics
cycle_metrics = linear_client.get_cycle_metrics_df()
user_metrics = linear_client.get_user_metrics_df()

with col1:
    st.metric(
        "Average Velocity",
        f"{cycle_metrics['velocity'].mean():.1f} pts/sprint"
    )

with col2:
    st.metric(
        "Average Throughput",
        f"{cycle_metrics['throughput'].mean():.1f} issues/sprint"
    )

with col3:
    completion_rate = (
        cycle_metrics['completed_story_points'].sum() /
        cycle_metrics['total_story_points'].sum() * 100
    )
    st.metric("Completion Rate", f"{completion_rate:.1f}%")

with col4:
    avg_time = cycle_metrics['avg_completion_time'].mean()
    st.metric("Avg Completion Time", f"{avg_time:.1f} hours")

# Velocity Trend
st.subheader("Team Velocity Trend")
velocity_trend = monte_carlo.get_velocity_trend()
fig_velocity = px.line(
    velocity_trend,
    x='start_date',
    y=['velocity', 'rolling_velocity'],
    title="Team Velocity Over Time",
    labels={
        'start_date': 'Sprint Start Date',
        'value': 'Story Points',
        'variable': 'Metric'
    }
)
st.plotly_chart(fig_velocity, use_container_width=True)

# Monte Carlo Forecast
st.subheader("Delivery Forecast")
story_points = st.number_input(
    "Story Points to Forecast",
    min_value=1.0,
    value=10.0,
    step=1.0
)

if st.button("Run Forecast"):
    forecast = monte_carlo.simulate_completion_time(story_points)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Expected Completion Time:")
        st.write(f"- 50% Confidence: {forecast['confidence_intervals']['confidence_50']:.1f} days")
        st.write(f"- 80% Confidence: {forecast['confidence_intervals']['confidence_80']:.1f} days")
        st.write(f"- 95% Confidence: {forecast['confidence_intervals']['confidence_95']:.1f} days")
    
    with col2:
        st.write("Expected Completion Date:")
        st.write(f"- Expected: {forecast['expected_completion_date'].strftime('%Y-%m-%d')}")
        st.write(f"- Earliest: {(datetime.now() + timedelta(days=forecast['min_days'])).strftime('%Y-%m-%d')}")
        st.write(f"- Latest: {(datetime.now() + timedelta(days=forecast['max_days'])).strftime('%Y-%m-%d')}")

# Team Member Performance
st.subheader("Team Member Performance")
user_performance = user_metrics.groupby('user_id').agg({
    'story_points_completed': 'sum',
    'velocity': 'mean',
    'capacity_utilization': 'mean'
}).reset_index()

fig_performance = go.Figure()
fig_performance.add_trace(go.Bar(
    x=user_performance['user_id'],
    y=user_performance['story_points_completed'],
    name='Total Story Points'
))
fig_performance.add_trace(go.Bar(
    x=user_performance['user_id'],
    y=user_performance['velocity'],
    name='Average Velocity'
))
fig_performance.update_layout(
    title="Individual Performance Metrics",
    barmode='group',
    xaxis_title="Team Member",
    yaxis_title="Story Points"
)
st.plotly_chart(fig_performance, use_container_width=True)

# Capacity Utilization
st.subheader("Capacity Utilization")
fig_capacity = px.bar(
    user_performance,
    x='user_id',
    y='capacity_utilization',
    title="Team Capacity Utilization",
    labels={
        'user_id': 'Team Member',
        'capacity_utilization': 'Capacity Utilization (%)'
    }
)
fig_capacity.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig_capacity, use_container_width=True)

# Forecast Accuracy
st.subheader("Forecast Accuracy Analysis")
accuracy_metrics = monte_carlo.analyze_historical_accuracy()

if accuracy_metrics.get('accuracy') is None:
    st.write("Not enough historical data for accuracy analysis")
else:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Forecast Bias",
            f"{accuracy_metrics['forecast_bias']:.1f} days"
        )
    
    with col2:
        st.metric(
            "Mean Absolute Error",
            f"{accuracy_metrics['mean_absolute_error']:.1f} days"
        )
    
    with col3:
        st.metric(
            "Within 80% Confidence",
            f"{accuracy_metrics['within_80_confidence']:.1f}%"
        )

# Cycle Time Distribution
st.subheader("Cycle Time Distribution")
cycle_times = cycle_metrics['avg_completion_time'].dropna()
fig_cycle_time = px.histogram(
    cycle_times,
    title="Distribution of Cycle Times",
    labels={'value': 'Cycle Time (hours)'}
)
st.plotly_chart(fig_cycle_time, use_container_width=True)

# Add data tables
with st.expander("View Raw Data"):
    st.subheader("Cycle Metrics")
    st.dataframe(cycle_metrics)
    
    st.subheader("User Metrics")
    st.dataframe(user_metrics)
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
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

# Get data with date filtering
@st.cache_data  # Simple caching without persistence
def get_filtered_data(start_date, end_date):
    cycle_metrics = linear_client.get_cycle_metrics_df()
    user_metrics = linear_client.get_user_metrics_df()
    daily_metrics = linear_client.get_daily_metrics_df()
    
    # Apply date filters
    # Convert date inputs to datetime for comparison
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date)
    
    # Filter cycle metrics
    filtered_cycle_metrics = cycle_metrics[
        (cycle_metrics['start_date'] >= start_datetime) &
        (cycle_metrics['end_date'] <= end_datetime)
    ]
    
    # Get valid cycle IDs
    valid_cycle_ids = filtered_cycle_metrics['cycle_id'].unique()
    
    # Filter user metrics using valid cycle IDs
    filtered_user_metrics = user_metrics[
        user_metrics['cycle_id'].isin(valid_cycle_ids)
    ]
    
    # Filter daily metrics
    filtered_daily_metrics = daily_metrics[
        (daily_metrics['date'] >= start_datetime) &
        (daily_metrics['date'] <= end_datetime)
    ]
    
    return filtered_cycle_metrics, filtered_user_metrics, filtered_daily_metrics

# Get filtered data
cycle_metrics, user_metrics, daily_metrics = get_filtered_data(
    date_range[0],
    date_range[1]
)

# Main dashboard
st.title("Linear.app Analytics Dashboard")

# Create tabs for better organization
tab1, tab2, tab3, tab4 = st.tabs([
    "Sprint Overview",
    "Team Performance",
    "Flow Metrics",
    "Forecasting"
])

with tab1:
    st.header("Sprint Overview")
    
    if not cycle_metrics.empty:
        # Top-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
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
            if cycle_metrics['total_story_points'].sum() > 0:
                completion_rate = (
                    cycle_metrics['completed_story_points'].sum() /
                    cycle_metrics['total_story_points'].sum() * 100
                )
                st.metric("Completion Rate", f"{completion_rate:.1f}%")
            else:
                st.metric("Completion Rate", "0.0%")
        
        with col4:
            avg_cycle = cycle_metrics['avg_cycle_time'].mean()
            st.metric("Avg Cycle Time", f"{avg_cycle:.1f} hours")
    else:
        st.warning("No cycle metrics available for the selected date range.")
    
    # Sprint Burn Charts
    st.subheader("Sprint Progress")
    
    # Get current sprint data
    if not daily_metrics.empty:
        current_sprint = daily_metrics.sort_values('date').iloc[-1]['cycle_id']
        sprint_data = daily_metrics[daily_metrics['cycle_id'] == current_sprint]
        
        if not sprint_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Burn Down Chart
                fig_burn_down = go.Figure()
                fig_burn_down.add_trace(go.Scatter(
                    x=sprint_data['date'],
                    y=sprint_data['remaining_hours'],
                    name='Actual Remaining Hours',
                    mode='lines+markers'
                ))
                
                # Add ideal burn down line
                initial_hours = sprint_data.iloc[0]['remaining_hours']
                ideal_burn = pd.DataFrame({
                    'date': sprint_data['date'],
                    'hours': np.linspace(initial_hours, 0, len(sprint_data))
                })
                fig_burn_down.add_trace(go.Scatter(
                    x=ideal_burn['date'],
                    y=ideal_burn['hours'],
                    name='Ideal Burn Down',
                    line=dict(dash='dash')
                ))
                
                fig_burn_down.update_layout(
                    title="Sprint Burn Down",
                    xaxis_title="Date",
                    yaxis_title="Remaining Hours"
                )
                st.plotly_chart(fig_burn_down, use_container_width=True)
            
            with col2:
                # Burn Up Chart
                fig_burn_up = go.Figure()
                fig_burn_up.add_trace(go.Scatter(
                    x=sprint_data['date'],
                    y=sprint_data['completed_points'],
                    name='Completed Points',
                    mode='lines+markers'
                ))
                
                # Add scope line
                scope_data = cycle_metrics[cycle_metrics['cycle_id'] == current_sprint]
                if not scope_data.empty:
                    scope = scope_data['total_story_points'].iloc[0]
                    fig_burn_up.add_trace(go.Scatter(
                        x=sprint_data['date'],
                        y=[scope] * len(sprint_data),
                        name='Sprint Scope',
                        line=dict(dash='dash')
                    ))
                
                fig_burn_up.update_layout(
                    title="Sprint Burn Up",
                    xaxis_title="Date",
                    yaxis_title="Story Points"
                )
                st.plotly_chart(fig_burn_up, use_container_width=True)
        else:
            st.warning("No sprint data available for the selected date range.")
    else:
        st.warning("No metrics data available yet. Please sync data from Linear first.")

with tab2:
    st.header("Team Performance")
    
    if not user_metrics.empty:
        # Team Member Performance
        user_performance = user_metrics.groupby('user_id').agg({
            'story_points_completed': 'sum',
            'velocity': 'mean',
            'capacity_utilization': 'mean',
            'efficiency_ratio': 'mean'
        }).reset_index()
        
        if not user_performance.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Velocity and Story Points
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
            
            with col2:
                # Efficiency Metrics
                fig_efficiency = go.Figure()
                fig_efficiency.add_trace(go.Bar(
                    x=user_performance['user_id'],
                    y=user_performance['capacity_utilization'],
                    name='Capacity Utilization %'
                ))
                fig_efficiency.add_trace(go.Bar(
                    x=user_performance['user_id'],
                    y=user_performance['efficiency_ratio'] * 100,
                    name='Efficiency Ratio %'
                ))
                fig_efficiency.update_layout(
                    title="Efficiency Metrics",
                    barmode='group',
                    xaxis_title="Team Member",
                    yaxis_title="Percentage"
                )
                st.plotly_chart(fig_efficiency, use_container_width=True)
        else:
            st.warning("No user performance data available for the selected date range.")
    else:
        st.warning("No user metrics available yet. Please sync data from Linear first.")
    
    # Velocity Trend
    st.subheader("Team Velocity Trend")
    velocity_trend = monte_carlo.get_velocity_trend()
    if not velocity_trend.empty:
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
    else:
        st.warning("No velocity trend data available yet.")

with tab3:
    st.header("Flow Metrics")
    
    if not daily_metrics.empty:
        # WIP and Blocked Items
        col1, col2 = st.columns(2)
        
        with col1:
            # WIP Over Time
            fig_wip = px.line(
                daily_metrics,
                x='date',
                y='wip_count',
                title="Work in Progress Over Time",
                labels={
                    'date': 'Date',
                    'wip_count': 'WIP Count'
                }
            )
            # Add WIP limit line
            fig_wip.add_hline(y=5, line_dash="dash", annotation_text="WIP Limit")
            st.plotly_chart(fig_wip, use_container_width=True)
        
        with col2:
            # Blocked Items Over Time
            fig_blocked = px.line(
                daily_metrics,
                x='date',
                y='blocked_items',
                title="Blocked Items Over Time",
                labels={
                    'date': 'Date',
                    'blocked_items': 'Blocked Items'
                }
            )
            st.plotly_chart(fig_blocked, use_container_width=True)
    else:
        st.warning("No daily metrics available for the selected date range.")
    
    if not cycle_metrics.empty:
        # Cycle Time Analytics
        st.subheader("Cycle Time Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Cycle Time Distribution
            cycle_times = cycle_metrics['avg_cycle_time'].dropna()
            if not cycle_times.empty:
                fig_cycle_time = px.histogram(
                    cycle_times,
                    title="Distribution of Cycle Times",
                    labels={'value': 'Cycle Time (hours)'}
                )
                st.plotly_chart(fig_cycle_time, use_container_width=True)
            else:
                st.warning("No cycle time data available.")
        
        with col2:
            # Lead Time Distribution
            lead_times = cycle_metrics['avg_lead_time'].dropna()
            if not lead_times.empty:
                fig_lead_time = px.histogram(
                    lead_times,
                    title="Distribution of Lead Times",
                    labels={'value': 'Lead Time (hours)'}
                )
                st.plotly_chart(fig_lead_time, use_container_width=True)
            else:
                st.warning("No lead time data available.")
        
        # Blocked Time Analysis
        st.subheader("Blocked Time Analysis")
        blocked_times = cycle_metrics['avg_blocked_time'].dropna()
        if not blocked_times.empty:
            fig_blocked_time = px.box(
                cycle_metrics,
                y='avg_blocked_time',
                title="Distribution of Blocked Time per Issue",
                labels={'avg_blocked_time': 'Average Blocked Time (hours)'}
            )
            st.plotly_chart(fig_blocked_time, use_container_width=True)
        else:
            st.warning("No blocked time data available.")
    else:
        st.warning("No cycle metrics available for the selected date range.")

with tab4:
    st.header("Forecasting")
    
    # Monte Carlo Forecast
    st.subheader("Delivery Forecast")
    story_points = st.number_input(
        "Story Points to Forecast",
        min_value=1.0,
        value=10.0,
        step=1.0
    )
    
    if not cycle_metrics.empty:
        if st.button("Run Forecast"):
            try:
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
                    st.write(f"- Earliest: {(datetime.now() + timedelta(days=int(forecast['min_days']))).strftime('%Y-%m-%d')}")
                    st.write(f"- Latest: {(datetime.now() + timedelta(days=int(forecast['max_days']))).strftime('%Y-%m-%d')}")
            except Exception as e:
                st.error(f"Error running forecast: {str(e)}")
    else:
        st.warning("No historical data available for forecasting. Please sync data from Linear first.")
    
    # Forecast Accuracy
    st.subheader("Forecast Accuracy Analysis")
    
    if not cycle_metrics.empty:
        try:
            accuracy_metrics = monte_carlo.analyze_historical_accuracy()
            
            if accuracy_metrics.get('accuracy') is None:
                st.info("Not enough historical data for accuracy analysis. Need at least 2 completed cycles.")
            else:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    bias = accuracy_metrics.get('forecast_bias', 0.0)
                    st.metric(
                        "Forecast Bias",
                        f"{bias:.1f} days",
                        delta=None if abs(bias) < 1 else f"{'Overestimating' if bias > 0 else 'Underestimating'}"
                    )
                
                with col2:
                    mae = accuracy_metrics.get('mean_absolute_error', 0.0)
                    st.metric(
                        "Mean Absolute Error",
                        f"{mae:.1f} days"
                    )
                
                with col3:
                    confidence = accuracy_metrics.get('within_80_confidence', 0.0)
                    st.metric(
                        "Within 80% Confidence",
                        f"{confidence:.1f}%",
                        delta=f"{confidence - 80:.1f}%" if confidence != 80 else None
                    )
        except Exception as e:
            st.error(f"Error analyzing forecast accuracy: {str(e)}")
    else:
        st.warning("No historical data available for accuracy analysis.")

# Add data tables
with st.expander("View Raw Data"):
    tab1, tab2, tab3 = st.tabs(["Cycle Metrics", "User Metrics", "Daily Metrics"])
    
    with tab1:
        st.dataframe(cycle_metrics)
    
    with tab2:
        st.dataframe(user_metrics)
    
    with tab3:
        st.dataframe(daily_metrics)
# Linear.app Analytics Dashboard

A comprehensive analytics and forecasting dashboard for Linear.app that provides insights into team productivity, sprint metrics, and delivery forecasting using Monte Carlo simulation.

## Features

- Real-time synchronization with Linear.app
- Comprehensive agile metrics tracking
- Sprint burn-down and burn-up charts
- Work in Progress (WIP) monitoring
- Blocked time analytics
- Individual performance analytics
- Capacity utilization monitoring
- Monte Carlo simulation for delivery forecasting
- Historical trend analysis
- Interactive Streamlit dashboard
- SQLite database for metrics storage

## Requirements

- Python 3.8+
- Linear.app API key
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository
2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip3 install -r requirements.txt
```

4. Create a `.env` file with your Linear API key:
```
linear_key=your_api_key_here
```

## Usage

1. Run the main script to sync data and launch the dashboard:
```bash
python3 main.py
```

2. Access the dashboard at http://localhost:8501

## Dashboard Features

### Sprint Overview
- Sprint velocity tracking
- Team throughput metrics
- Completion rates
- Sprint burn-down charts
- Sprint burn-up charts
- Scope change tracking

### Team Performance
- Individual velocity metrics
- Story point completion rates
- Capacity utilization
- Efficiency ratios (ideal vs actual hours)
- Historical performance trends

### Flow Metrics
- Work in Progress (WIP) tracking
- WIP limits visualization
- Blocked items monitoring
- Cycle time distribution
- Lead time analytics
- Blocked time analysis

### Forecasting
- Monte Carlo simulation for delivery dates
- Confidence intervals (50%, 80%, 95%)
- Historical accuracy analysis
- Velocity trends
- Throughput forecasting

### Data Tables
- Detailed cycle metrics
- User performance data
- Daily metrics tracking
- Raw data export capabilities

## Database Schema

The application uses SQLite with the following tables:

### Core Tables
- Users: Team member information
- Cycles: Sprint/iteration data
- Issues: Ticket information with estimates and actual hours

### Tracking Tables
- BlockedPeriod: Records of when issues were blocked
- IssueStateChange: State transition history
- DailyMetrics: Daily sprint metrics

### Metrics Tables
- CycleCapacity: Team member capacity per sprint
- CycleMetrics: Comprehensive sprint-level metrics
- UserMetrics: Individual performance metrics
- MonteCarloForecast: Delivery forecasts

## Metrics Definitions

### Sprint Metrics
- Sprint Velocity: Story points completed in a sprint
- Capacity: Available hours for coding (typically 75-80% of total hours)
- Throughput: Completed work items per sprint
- Story Points: Fibonacci sequence estimates (1-2-3-5-8-13)
- Ideal Hours: Estimated "heads-down" work time
- Sprint Burn Down: Daily remaining hours vs ideal trend
- Sprint Burn Up: Completed story points vs sprint scope

### Flow Metrics
- Cycle Time: Time from work start to completion
- Lead Time: Time from backlog to completion
- Blocked Time: Duration when work cannot progress
- WIP: Current items in progress
- WIP Limit: Maximum allowed concurrent work items

## Configuration

### Environment Variables
- `linear_key`: Your Linear.app API key

### Customization
- Default sprint capacity: 32 productive hours (80% of 40-hour week)
- Default WIP limit: 5 items per team
- Monte Carlo simulation runs: 10,000 (adjustable in forecasting.py)
- Dashboard refresh rate: Real-time
- Date range filters: 90 days default (adjustable in dashboard)
- Story point sequence: Fibonacci (1-2-3-5-8-13)

### Performance Settings
- Daily metrics calculation frequency
- Historical data retention period
- Graph update intervals
- Data sync frequency

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License
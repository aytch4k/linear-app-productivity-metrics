# Linear.app Analytics Dashboard

A comprehensive analytics and forecasting dashboard for Linear.app that provides insights into team productivity, sprint metrics, and delivery forecasting using Monte Carlo simulation.

## Features

- Real-time synchronization with Linear.app
- Sprint and team metrics tracking
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

### Metrics Overview
- Sprint velocity
- Team throughput
- Completion rates
- Average cycle times

### Forecasting
- Monte Carlo simulation for delivery dates
- Confidence intervals (50%, 80%, 95%)
- Historical accuracy analysis
- Velocity trends

### Team Analytics
- Individual performance metrics
- Capacity utilization
- Story point completion rates
- Cycle time distribution

### Data Tables
- Detailed cycle metrics
- User performance data
- Raw data export capabilities

## Database Schema

The application uses SQLite with the following main tables:

- Users: Team member information
- Cycles: Sprint/iteration data
- Issues: Ticket information
- CycleCapacity: Team member capacity per sprint
- CycleMetrics: Sprint-level metrics
- UserMetrics: Individual performance metrics
- MonteCarloForecast: Delivery forecasts

## Configuration

### Environment Variables
- `linear_key`: Your Linear.app API key

### Customization
- Default sprint capacity: 40 hours (adjustable in linear_client.py)
- Monte Carlo simulation runs: 10,000 (adjustable in forecasting.py)
- Dashboard refresh rate: Real-time
- Date range filters: 90 days default (adjustable in dashboard)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License
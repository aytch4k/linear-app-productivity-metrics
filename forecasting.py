import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, List, Dict
from scipy import stats
from database import init_db, MonteCarloForecast, CycleMetrics, UserMetrics
import pandas as pd

class MonteCarloSimulator:
    def __init__(self, db_session=None):
        self.db = db_session or init_db()
        
    def get_historical_metrics(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch historical metrics for analysis"""
        cycle_metrics = pd.read_sql(
            self.db.query(CycleMetrics).statement,
            self.db.bind
        )
        user_metrics = pd.read_sql(
            self.db.query(UserMetrics).statement,
            self.db.bind
        )
        return cycle_metrics, user_metrics

    def calculate_completion_distribution(self, cycle_metrics: pd.DataFrame) -> Tuple[float, float]:
        """Calculate mean and std dev of completion rates"""
        velocities = cycle_metrics['velocity'].dropna()
        if len(velocities) < 2:
            return 10.0, 2.0  # Default values if not enough data
        
        # Use log-normal distribution as completion times can't be negative
        log_velocities = np.log(velocities)
        return log_velocities.mean(), log_velocities.std()

    def simulate_completion_time(
        self,
        story_points: float,
        n_simulations: int = 10000,
        confidence_levels: List[float] = [0.5, 0.8, 0.95]
    ) -> Dict:
        """
        Run Monte Carlo simulation to forecast completion dates
        
        Args:
            story_points: Total story points to complete
            n_simulations: Number of simulations to run
            confidence_levels: Confidence levels to calculate
            
        Returns:
            Dict containing simulation results and confidence intervals
        """
        cycle_metrics, _ = self.get_historical_metrics()
        mu, sigma = self.calculate_completion_distribution(cycle_metrics)
        
        # Generate random completion rates from log-normal distribution
        completion_rates = np.random.lognormal(mu, sigma, n_simulations)
        
        # Calculate completion times in days
        completion_times = story_points / completion_rates
        
        # Calculate confidence intervals
        confidence_intervals = {
            f'confidence_{int(level*100)}': np.percentile(completion_times, level*100)
            for level in confidence_levels
        }
        
        # Calculate expected completion date
        now = datetime.now()
        expected_days = np.mean(completion_times)
        expected_completion = now + timedelta(days=expected_days)
        
        # Store forecast in database
        forecast = MonteCarloForecast(
            simulation_date=now,
            story_points=story_points,
            confidence_50=confidence_intervals['confidence_50'],
            confidence_80=confidence_intervals['confidence_80'],
            confidence_95=confidence_intervals['confidence_95'],
            min_completion_date=now + timedelta(days=min(completion_times)),
            max_completion_date=now + timedelta(days=max(completion_times)),
            expected_completion_date=expected_completion
        )
        self.db.add(forecast)
        self.db.commit()
        
        return {
            'story_points': story_points,
            'expected_days': expected_days,
            'expected_completion_date': expected_completion,
            'confidence_intervals': confidence_intervals,
            'min_days': min(completion_times),
            'max_days': max(completion_times),
            'simulation_count': n_simulations
        }

    def analyze_historical_accuracy(self) -> Dict:
        """Analyze accuracy of past forecasts compared to actual completion times"""
        forecasts = pd.read_sql(
            self.db.query(MonteCarloForecast).statement,
            self.db.bind
        )
        
        if len(forecasts) < 2:
            return {
                'accuracy': None,
                'message': 'Not enough historical forecast data for accuracy analysis'
            }
        
        # Compare forecasted dates with actual completion dates
        cycle_metrics = pd.read_sql(
            self.db.query(CycleMetrics).statement,
            self.db.bind
        )
        
        accuracy_metrics = {
            'forecast_bias': 0.0,  # Positive means overestimation
            'mean_absolute_error': 0.0,
            'within_50_confidence': 0.0,
            'within_80_confidence': 0.0,
            'within_95_confidence': 0.0
        }
        
        # Calculate accuracy metrics
        # This is a simplified version - in practice you'd want to match
        # forecasts with actual completion dates more precisely
        for _, forecast in forecasts.iterrows():
            actual_completion = cycle_metrics[
                cycle_metrics['total_story_points'] >= forecast['story_points']
            ]['end_date'].min()
            
            if pd.notnull(actual_completion):
                forecast_date = forecast['expected_completion_date']
                difference = (actual_completion - forecast_date).days
                
                accuracy_metrics['forecast_bias'] += difference
                accuracy_metrics['mean_absolute_error'] += abs(difference)
                
                # Check if actual completion was within confidence intervals
                if actual_completion <= forecast_date + timedelta(days=forecast['confidence_50']):
                    accuracy_metrics['within_50_confidence'] += 1
                if actual_completion <= forecast_date + timedelta(days=forecast['confidence_80']):
                    accuracy_metrics['within_80_confidence'] += 1
                if actual_completion <= forecast_date + timedelta(days=forecast['confidence_95']):
                    accuracy_metrics['within_95_confidence'] += 1
        
        n_forecasts = len(forecasts)
        accuracy_metrics['forecast_bias'] /= n_forecasts
        accuracy_metrics['mean_absolute_error'] /= n_forecasts
        accuracy_metrics['within_50_confidence'] = (
            accuracy_metrics['within_50_confidence'] / n_forecasts * 100
        )
        accuracy_metrics['within_80_confidence'] = (
            accuracy_metrics['within_80_confidence'] / n_forecasts * 100
        )
        accuracy_metrics['within_95_confidence'] = (
            accuracy_metrics['within_95_confidence'] / n_forecasts * 100
        )
        
        return accuracy_metrics

    def get_velocity_trend(self) -> pd.DataFrame:
        """Analyze team velocity trends over time"""
        cycle_metrics = pd.read_sql(
            self.db.query(CycleMetrics).statement,
            self.db.bind
        )
        
        if len(cycle_metrics) < 2:
            return pd.DataFrame()
        
        # Calculate rolling averages and trends
        cycle_metrics = cycle_metrics.sort_values('start_date')
        cycle_metrics['rolling_velocity'] = (
            cycle_metrics['velocity'].rolling(window=3, min_periods=1).mean()
        )
        cycle_metrics['velocity_trend'] = (
            cycle_metrics['velocity'].rolling(window=3, min_periods=1).apply(
                lambda x: stats.linregress(range(len(x)), x)[0]
            )
        )
        
        return cycle_metrics[['start_date', 'velocity', 'rolling_velocity', 'velocity_trend']]
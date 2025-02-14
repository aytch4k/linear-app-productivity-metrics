from linear_client import LinearMetricsClient
from database import init_db
import subprocess
import sys
import os

def sync_data():
    """Initialize database and sync data from Linear"""
    print("Initializing database...")
    db = init_db()
    
    print("Testing Linear API connection...")
    client = LinearMetricsClient()
    if not client.test_connection():
        print("Failed to connect to Linear API. Please check your API key and try again.")
        sys.exit(1)
    
    print("Syncing data from Linear...")
    client.sync_data()
    print("Data sync complete!")

def launch_dashboard():
    """Launch the Streamlit dashboard"""
    print("Launching dashboard...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py"])

def main():
    # Ensure we're in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    try:
        # Sync data and launch dashboard
        sync_data()
        launch_dashboard()
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
from flask import Flask
from app import app
import schedule
import time
import threading
from datetime import datetime
from simplified_enhanced_fetcher import EnhancedDataFetcher  # Updated import
import sqlite3

# Initialize enhanced data fetcher
data_fetcher = EnhancedDataFetcher(get_db_path())
def get_db_path():
    """Get the correct database path based on environment."""
    import os
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV') or not os.access('.', os.W_OK):
        return '/tmp/virtual_football.db'
    else:
        return 'virtual_football.db'
def update_data():
    """Fetch and update both completed and scheduled matches using enhanced fetcher."""
    print(f"Starting FULL data update at {datetime.now()}")
    
    try:
        # Use the corrected full update method
        success = data_fetcher.run_full_update()
        
        if success:
            print("Full data update completed successfully")
        else:
            print("Full data update had some issues - will retry next cycle")
            
    except Exception as e:
        print(f"Error in full data update cycle: {e}")

def update_scheduled_matches_only():
    """Quick update for just scheduled matches."""
    print(f"Updating scheduled matches at {datetime.now()}")
    
    try:
        # Use the corrected scheduled update method
        success = data_fetcher.run_scheduled_update()
        
        if success:
            print("Scheduled matches updated successfully")
        else:
            print("Scheduled matches update failed")
            
    except Exception as e:
        print(f"Error updating scheduled matches: {e}")

def update_completed_matches_only():
    """Update only completed matches via API."""
    print(f"Updating completed matches via API at {datetime.now()}")
    
    try:
        # Use the corrected completed matches update method (API only, no Selenium)
        success = data_fetcher.run_completed_update()
        
        if success:
            print("Completed matches updated successfully via API")
        else:
            print("Completed matches API update failed")
            
    except Exception as e:
        print(f"Error updating completed matches: {e}")

def check_for_finished_matches():
    """Check if any matches finished 1 minute ago (31 minutes after start) and trigger update."""
    try:
        with sqlite3.connect('virtual_football.db') as conn:
            cursor = conn.cursor()
            
            # Get current time in milliseconds
            current_time_ms = int(time.time() * 1000)
            
            # Calculate 31 minutes ago (30 min match + 1 min buffer)
            match_end_time_ms = current_time_ms - (31 * 60 * 1000)  # 31 minutes ago
            tolerance_ms = 60 * 1000  # 1 minute tolerance window
            
            # Find matches that should have finished around this time
            cursor.execute('''
                SELECT event_id, home_team, away_team, start_time 
                FROM scheduled_matches 
                WHERE start_time BETWEEN ? AND ? 
                AND status = 'scheduled'
            ''', (match_end_time_ms - tolerance_ms, match_end_time_ms + tolerance_ms))
            
            finished_matches = cursor.fetchall()
            
            if finished_matches:
                print(f"Found {len(finished_matches)} matches that should be finished - triggering update")
                # Trigger completed matches update to get final results
                update_completed_matches_only()
                
                # Mark these matches as processed
                for match in finished_matches:
                    cursor.execute('''
                        UPDATE scheduled_matches 
                        SET status = 'finished' 
                        WHERE event_id = ?
                    ''', (match[0],))
                conn.commit()
                
    except Exception as e:
        print(f"Error checking for finished matches: {e}")

def check_for_started_matches():
    """Check if any scheduled matches have started and trigger update 1 minute later."""
    try:
        with sqlite3.connect('virtual_football.db') as conn:
            cursor = conn.cursor()
            
            # Get current time in milliseconds
            current_time_ms = int(time.time() * 1000)
            one_minute_ago_ms = current_time_ms - (2 * 60 * 1000)  # 1 minute ago
            
            # Find matches that started in the last minute
            cursor.execute('''
                SELECT event_id, home_team, away_team, start_time 
                FROM scheduled_matches 
                WHERE start_time BETWEEN ? AND ? 
                AND status = 'scheduled'
            ''', (one_minute_ago_ms, current_time_ms))
            
            started_matches = cursor.fetchall()
            
            if started_matches:
                print(f"Found {len(started_matches)} matches that just started - triggering update")
                # Trigger completed matches update to get results
                update_completed_matches_only()
                
                # Mark these matches as processed to avoid repeated updates
                for match in started_matches:
                    cursor.execute('''
                        UPDATE scheduled_matches 
                        SET status = 'started' 
                        WHERE event_id = ?
                    ''', (match[0],))
                conn.commit()
                
    except Exception as e:
        print(f"Error checking for started matches: {e}")

def run_scheduler():
    """Run data update scheduler in a separate thread with optimized timing."""
    # Schedule different types of updates at different intervals
    
    # Full comprehensive update every 30 minutes
    #schedule.every(30).minutes.do(update_data)
    
    # Quick scheduled matches update every 10 minutes
    schedule.every(10).minutes.do(update_scheduled_matches_only)
    
    # Completed matches API update every 5 minutes (since it's just API calls, can be more frequent)
    # schedule.every(5).minutes.do(update_completed_matches_only)
    
    schedule.every(1).minutes.do(check_for_started_matches)
    schedule.every(1).minutes.do(check_for_finished_matches)
    # Initial data fetch on startup
    print("Running initial data fetch...")
    try:
        print("1. Initial completed matches fetch...")
        update_completed_matches_only()
        time.sleep(5)  # Small delay between updates
        
        print("2. Initial scheduled matches fetch...")
        update_scheduled_matches_only()
    except Exception as e:
        print(f"Initial data fetch failed: {e}")
        print("Will continue with scheduled updates...")
    
    print("\nData scheduler started with the following schedule:")
    print("- Full update: Every 30 minutes") 
    print("- Scheduled matches (Selenium): Every 10 minutes")
    print("- Completed matches (API): Every 5 minutes")
    print("-" * 50)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("Scheduler stopped by user")
            break
        except Exception as e:
            print(f"Scheduler error: {e}")
            time.sleep(60)  # Continue despite errors

def manual_data_update():
    """Manual data update function for testing."""
    print("Manual data update triggered...")
    update_data()

def test_api_only():
    """Test only the API functionality for completed matches."""
    print("Testing API-only completed matches fetch...")
    update_completed_matches_only()

def test_selenium_only():
    """Test only the Selenium functionality for scheduled matches."""
    print("Testing Selenium-only scheduled matches fetch...")
    update_scheduled_matches_only()

if __name__ == '__main__':
    print("Virtual Football Prediction System - Enhanced")
    print("=" * 60)
    
    # Check if we should run specific tests
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == '--update':
            print("Running manual full update...")
            manual_data_update()
            exit(0)
        elif sys.argv[1] == '--scheduled-only':
            print("Running scheduled matches update only...")
            test_selenium_only()
            exit(0)
        elif sys.argv[1] == '--completed-only':
            print("Running completed matches API update only...")
            test_api_only()
            exit(0)
        elif sys.argv[1] == '--test-api':
            print("Testing API connectivity...")
            test_api_only()
            exit(0)
    
    # Start scheduler in a background thread
    print("Starting background data scheduler...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Give scheduler a moment to start
    time.sleep(2)
    
    # Run Flask app
    print("Starting Flask web server...")
    print("Web interface will be available at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        # Cleanup on exit
        print("Cleanup completed")
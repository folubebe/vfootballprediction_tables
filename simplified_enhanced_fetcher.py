import os
import time
import sqlite3
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from config import standardize_league_name, debug_league_mapping

# Import your existing API client and processors
try:
    from api_client import VirtualFootballAPI, DataProcessor, DatabaseManager, LeagueTableGenerator
    print("Successfully imported API components")
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure api_client.py is in the same directory")

class EnhancedDataFetcher:
    """Enhanced data fetcher combining API calls for completed matches and Selenium for scheduled matches."""
    
    def __init__(self, db_path='virtual_football.db'):
        self.db_path = db_path
        self.driver = None
        self.config = {
            'urls': {
                'schedule': 'https://www.sportybet.com/ng/sport/vfootball?time=1',
                'schedule_12h': 'https://www.sportybet.com/ng/sport/vfootball/today',
            },
            'retry_delay': 2,
            'page_load_delay': 3
        }
        self.processed_scheduled = []
        self.existing_scheduled_ids = set()
        
        # Initialize API components for completed matches
        self.api_client = VirtualFootballAPI()
        self.data_processor = DataProcessor()
        self.db_manager = DatabaseManager(db_path)
        
        # Initialize database with missing tables
        self._ensure_database_tables()
        
        # Debug mode flag
        self.debug = True
    
    def _ensure_database_tables(self):
        """Ensure all required database tables exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create scheduled_matches table with all required columns
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scheduled_matches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE,
                        home_team TEXT,
                        away_team TEXT,
                        league TEXT,
                        start_time INTEGER,
                        match_time_display TEXT,
                        status TEXT DEFAULT 'scheduled',
                        home_odds REAL DEFAULT 1.0,
                        draw_odds REAL DEFAULT 1.0,
                        away_odds REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                print("Database tables ensured successfully")
        except sqlite3.Error as e:
            print(f"Error ensuring database tables: {e}")
    
    def initialize_driver(self):
        """Initialize WebDriver with your proven configuration."""
        try:
            chrome_options = ChromeOptions()
            # Uncomment next line for headless mode
            # chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1280,720")
            
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("WebDriver initialized successfully")
            return True
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            return False
    
    def navigate_to_page(self, page_num: int) -> bool:
        """Navigate to specific page using your logic."""
        if not self.driver:
            return False
            
        try:
            # Scroll to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            
            # Check current page first
            try:
                current_page_element = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "span.pageNum.selected"))
                )
                current_page_num = int(current_page_element.text)
            except:
                current_page_num = 1
            
            # Skip if already on target page
            if current_page_num == page_num:
                return True
            
            # Navigate to target page
            page_element = self.driver.find_element(
                By.XPATH, f'//span[@class="pageNum" and text()="{page_num}"]'
            )
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", page_element)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", page_element)
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error navigating to page {page_num}: {e}")
            return False
    
    def _load_existing_scheduled_ids(self):
        """Load existing scheduled match IDs from database to prevent duplicates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT event_id FROM scheduled_matches')
                self.existing_scheduled_ids = {row[0] for row in cursor.fetchall()}
                print(f"Loaded {len(self.existing_scheduled_ids)} existing scheduled match IDs")
        except sqlite3.Error as e:
            print(f"Error loading existing scheduled IDs: {e}")
            self.existing_scheduled_ids = set()
    
    def _clean_old_scheduled_matches(self):
        """Clean up old scheduled matches that might be outdated."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Remove scheduled matches older than 24 hours
                cutoff_time = (datetime.now() - timedelta(hours=24)).timestamp() * 1000
                cursor.execute('DELETE FROM scheduled_matches WHERE start_time < ?', (cutoff_time,))
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} old scheduled matches")
        except sqlite3.Error as e:
            print(f"Error cleaning old scheduled matches: {e}")
    
    def fetch_scheduled_matches(self, max_pages=None):
        """Fetch scheduled matches using Selenium with no page limit."""
        if not self.driver:
            if not self.initialize_driver():
                return []
        
        # Load existing scheduled match IDs to prevent duplicates
        self._load_existing_scheduled_ids()
        
        wait = WebDriverWait(self.driver, 10)
        self.driver.get(self.config['urls']['schedule'])
        time.sleep(self.config['page_load_delay'])
        
        all_scheduled_matches = []
        
        try:
            # Get total available pages
            try:
                page_elements = wait.until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "pageNum"))
                )
                max_available_pages = max(1, len(page_elements) - 2)  # Subtract prev/next buttons
                pages_to_process = max_pages if max_pages else max_available_pages
                print(f"Processing {pages_to_process} schedule pages out of {max_available_pages} available")
            except TimeoutException:
                pages_to_process = 1
                print("Could not determine total pages, processing single page")
            
            for page_num in range(1, pages_to_process + 1):
                print(f"Processing schedule page {page_num}/{pages_to_process}")
                
                # Navigate to page (skip for first page)
                if page_num > 1:
                    self.driver.get(self.config['urls']['schedule'])
                    time.sleep(self.config['page_load_delay'])
                    if not self.navigate_to_page(page_num):
                        print(f"Failed to navigate to page {page_num}, stopping")
                        break
                
                # Extract matches from this page
                page_matches = self._extract_matches_from_page()
                
                # Filter out duplicates
                new_matches = [match for match in page_matches if match['event_id'] not in self.existing_scheduled_ids]
                
                all_scheduled_matches.extend(new_matches)
                
                print(f"Extracted {len(page_matches)} matches from page {page_num}, {len(new_matches)} are new")
                
        except Exception as e:
            print(f"Error fetching scheduled matches: {e}")
        
        print(f"Total new scheduled matches fetched: {len(all_scheduled_matches)}")
        self.processed_scheduled = all_scheduled_matches
        return all_scheduled_matches
    
    def fetch_completed_matches_via_api(self):
        """Fetch completed matches using your existing API client."""
        print("Fetching completed matches via API...")
        
        try:
            # Use your existing API client to fetch all leagues
            all_league_data = self.api_client.fetch_all_leagues(days_back=0)  # Today only
            
            if not all_league_data:
                print("No completed match data fetched from API")
                return False
            
            print(f"Successfully fetched data from {len(all_league_data)} leagues via API")
            
            total_matches_processed = 0
            
            # Process each league
            for league_name, league_pages in all_league_data.items():
                print(f"Processing {league_name.title()} League via API...")
                
                matches = self.data_processor.process_league_pages(league_pages)
                
                if not matches:
                    print(f"No matches found for {league_name}")
                    continue
                
                # IMPORTANT: Standardize league names for each match before saving
                for match in matches:
                    original_league = match.get('league', 'unknown')
                    standardized_league = standardize_league_name(original_league)
                    match['league'] = standardized_league
                    
                    if self.debug and original_league != standardized_league:
                        print(f"  Standardized: '{original_league}' -> '{standardized_league}'")
                
                # Save matches to database using standardized league name
                standardized_league_name = standardize_league_name(league_name)
                self.db_manager.save_matches(matches, standardized_league_name)
                
                # Generate and save league table
                table_generator = LeagueTableGenerator()
                
                for match in matches:
                    table_generator.add_match(match)
                
                league_table = table_generator.generate_table()
                self.db_manager.save_league_table(league_table, standardized_league_name)
                
                total_matches_processed += len(matches)
                print(f"Processed {len(matches)} matches for {standardized_league_name}")
            
            print(f"Total completed matches processed via API: {total_matches_processed}")
            return True
            
        except Exception as e:
            print(f"Error fetching completed matches via API: {e}")
            return False


    def _parse_time_to_timestamp(self, time_str):
        """Convert time string like '15:34' to proper future timestamp"""
        from datetime import datetime, timedelta
        import re
        
        if not time_str or time_str == "Pre-match":
            return int((time.time() + 600) * 1000)
        
        time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            
            now = datetime.now()
            target_time = datetime(now.year, now.month, now.day, hour, minute, 0)
            
            if target_time <= now:
                target_time += timedelta(days=1)
            
            return int(target_time.timestamp() * 1000)
        
        return int((time.time() + 900) * 1000)


    def _extract_matches_from_page(self):
        """Extract matches from current page using your exact logic with proper league standardization."""
        wait = WebDriverWait(self.driver, 10)
        page_matches = []
        
        try:
            # Find all league sections
            league_sections = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'match-league-wrap'))
            )
            
            # Extract matches from each league section
            for league_section in league_sections:
                try:
                    # Get league name
                    league_title_element = league_section.find_element(By.CLASS_NAME, 'league-title')
                    raw_league_name = league_title_element.find_element(By.CLASS_NAME, 'text').text.strip()
                    
                    # CRITICAL FIX: Standardize the league name immediately
                    standardized_league_name = standardize_league_name(raw_league_name)
                    
                    if self.debug:
                        print(f"League name processing: '{raw_league_name}' -> '{standardized_league_name}'")
                    
                    # Get all matches in this league
                    league_matches = league_section.find_elements(By.CLASS_NAME, 'm-table-row.m-content-row.match-row')
                    
                    # Extract data for each match
                    for match in league_matches:
                        try:
                            # Extract game details using your exact selectors
                            try:
                                match_time1 = match.find_element(By.CLASS_NAME, 'time').text.replace('\n', '')
                                match_time = match.find_element(By.CLASS_NAME, 'time').text.replace('\n', '')
                                match_time = self._parse_time_to_timestamp(match_time)
                            except:
                                match_time = "Pre-match"
                            
                            teams_title = match.find_element(By.CLASS_NAME, 'teams').get_attribute('title')
                            
                            # Parse team names
                            if ' vs ' in teams_title:
                                home_team, away_team = teams_title.split(' vs ')
                            else:
                                # Handle other possible formats
                                teams = teams_title.split(' - ')
                                if len(teams) >= 2:
                                    home_team, away_team = teams[0], teams[1]
                                else:
                                    continue  # Skip if can't parse teams
                            
                            # Create unique match ID to prevent duplicates
                            # normalized_time = match_time.replace(':', '').replace(' ', '') if match_time != "Pre-match" else "prematch"
                            normalized_time = match_time if match_time != "Pre-match" else "prematch"
                            unique_match_id = f"{home_team.strip()}_{away_team.strip()}_{standardized_league_name}_{normalized_time}"
                            
                            # Get match ID from element or use our generated one
                            try:
                                element_match_id = match.find_element(By.CLASS_NAME, 'teams').get_attribute('data-match-id')
                                if element_match_id:
                                    match_id = element_match_id
                                else:
                                    match_id = unique_match_id
                            except:
                                match_id = unique_match_id
                            
                            # For scheduled games, we might not have scores yet
                            try:
                                score_text = match.find_element(By.CLASS_NAME, 'score').text
                                if score_text and '-' in score_text:
                                    score_parts = score_text.split('-')
                                    home_score = int(score_parts[0].strip())
                                    away_score = int(score_parts[1].strip())
                                else:
                                    home_score, away_score = 0, 0
                            except:
                                home_score, away_score = 0, 0
                            
                            # Get odds if available
                            try:
                                odds_elements = match.find_elements(By.CLASS_NAME, 'm-outcome')
                                if len(odds_elements) >= 3:
                                    home_odds = float(odds_elements[0].text) if odds_elements[0].text else 1.0
                                    draw_odds = float(odds_elements[1].text) if odds_elements[1].text else 1.0
                                    away_odds = float(odds_elements[2].text) if odds_elements[2].text else 1.0
                                else:
                                    home_odds = draw_odds = away_odds = 1.0
                            except:
                                home_odds = draw_odds = away_odds = 1.0
                            
                            # Create match data with STANDARDIZED league name
                            match_data = {
                                'event_id': match_id,
                                'home_team': home_team.strip(),
                                'away_team': away_team.strip(),
                                'league': standardized_league_name,  # Use standardized name here
                                'start_time': self._parse_time_to_timestamp(match_time1),  
                                'match_time_display': datetime.fromtimestamp(match_time / 1000),
                                'home_score': home_score,
                                'away_score': away_score,
                                'home_odds': home_odds,
                                'draw_odds': draw_odds,
                                'away_odds': away_odds,
                                'status': 'scheduled'
                            }
                            
                            page_matches.append(match_data)
                            
                            if self.debug:
                                print(f"  Added match: {home_team.strip()} vs {away_team.strip()} [{standardized_league_name}]")
                            
                        except Exception as e:
                            print(f"Error extracting individual match data: {e}")
                            continue
                        
                except Exception as e:
                    print(f"Error processing league section: {e}")
                    continue
                    
        except TimeoutException:
            print("No league sections found on this page")
        except Exception as e:
            print(f"Error extracting matches from page: {e}")
            # Try to refresh page on error
            try:
                self.driver.refresh()
                time.sleep(self.config['page_load_delay'])
            except:
                pass
                
        return page_matches
    
    def save_to_database(self):
        """Save scheduled matches to database with duplicate prevention."""
        if not self.processed_scheduled:
            print("No scheduled matches to save")
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean old scheduled matches first
                self._clean_old_scheduled_matches()
                
                # Save scheduled matches with duplicate checking
                new_scheduled_count = 0
                for match in self.processed_scheduled:
                    try:
                        # Ensure league name is standardized before saving
                        standardized_league = standardize_league_name(match['league'])
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO scheduled_matches 
                            (event_id, home_team, away_team, league, start_time, status, match_time_display, home_odds, draw_odds, away_odds)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            match['event_id'],
                            match['home_team'],
                            match['away_team'],
                            standardized_league,  # Use standardized name
                            match['start_time'],
                            match.get('status', 'scheduled'),
                            match.get('match_time_display', ''),
                            match.get('home_odds', 1.0),
                            match.get('draw_odds', 1.0),
                            match.get('away_odds', 1.0)
                        ))
                        if cursor.rowcount > 0:  # New row was inserted
                            new_scheduled_count += 1
                            if self.debug:
                                print(f"  Saved: {match['home_team']} vs {match['away_team']} [{standardized_league}]")
                    except sqlite3.Error as e:
                        print(f"Error saving scheduled match {match['event_id']}: {e}")
                        continue
                
                print(f"Saved {new_scheduled_count} new scheduled matches (filtered {len(self.processed_scheduled) - new_scheduled_count} duplicates)")
                conn.commit()
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
    
    def cleanup_old_scheduled_matches(self):
        """Remove scheduled matches that have already started"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time_ms = int(time.time() * 1000)
                
                cursor.execute('DELETE FROM scheduled_matches WHERE start_time < ?', (current_time_ms,))
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    print(f"Cleaned up {deleted} old scheduled matches")
        except Exception as e:
            print(f"Error cleaning up old matches: {e}")


    def run_full_update(self):
        """Run both scheduled and completed matches update."""
        print("Starting full data update...")
        
        success = True
        
        try:
            # First, fetch completed matches via API (no Selenium needed)
            print("1. Fetching completed matches via API...")
            api_success = self.fetch_completed_matches_via_api()
            if not api_success:
                print("API fetch failed, but continuing with scheduled matches")
                success = False
            
            # Then, fetch scheduled matches via Selenium
            print("2. Fetching scheduled matches via Selenium...")
            if not self.initialize_driver():
                print("Failed to initialize driver for scheduled matches")
                return False
            
            scheduled_matches = self.fetch_scheduled_matches()
            
            if scheduled_matches:
                self.save_to_database()
                print(f"Successfully processed {len(scheduled_matches)} scheduled matches")
            else:
                print("No scheduled matches found")
            
            print("Full data update completed")
            return success
            
        except Exception as e:
            print(f"Error in full data update: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                print("WebDriver closed")
    
    def run_scheduled_update(self):
        """Run scheduled matches update only."""
        print("Starting scheduled matches update...")
        
        try:

            # Clean up old matches FIRST
            self.cleanup_old_scheduled_matches()
            # Initialize driver
            if not self.initialize_driver():
                return False
            
            # Fetch scheduled matches
            print("Fetching scheduled matches...")
            self.fetch_scheduled_matches()
            
            # Save to database
            print("Saving to database...")
            self.save_to_database()
            
            print("Scheduled matches update completed successfully")
            return True
            
        except Exception as e:
            print(f"Error in scheduled matches update: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                print("WebDriver closed")
    
    def run_completed_update(self):
        """Run completed matches update only (via API)."""
        print("Starting completed matches update via API...")
        
        try:
            success = self.fetch_completed_matches_via_api()
            
            if success:
                print("Completed matches update completed successfully")
            else:
                print("Completed matches update failed")
                
            return success
            
        except Exception as e:
            print(f"Error in completed matches update: {e}")
            return False
    
    def debug_database_status(self):
        """Debug function to check database status after updates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                print("\n" + "="*60)
                print("DATABASE STATUS AFTER UPDATE:")
                print("="*60)
                
                # Check league distribution
                for table_name, league_column in [('matches', 'league'), ('scheduled_matches', 'league'), ('league_tables', 'league_name')]:
                    print(f"\n{table_name.upper()}:")
                    cursor.execute(f'SELECT {league_column}, COUNT(*) FROM {table_name} GROUP BY {league_column} ORDER BY COUNT(*) DESC')
                    results = cursor.fetchall()
                    for league, count in results:
                        print(f"  {league}: {count} records")
                
                # Check for potential matches that can be predicted
                print(f"\nPOTENTIAL PREDICTIONS:")
                cursor.execute('''
                    SELECT s.league, s.home_team, s.away_team,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM matches m 
                               WHERE m.league = s.league 
                               AND (m.home_team = s.home_team OR m.away_team = s.home_team)
                               AND (m.home_team = s.away_team OR m.away_team = s.away_team)
                           ) THEN 'YES' ELSE 'NO' END as can_predict
                    FROM scheduled_matches s
                    ORDER BY can_predict DESC, s.league, s.home_team
                    LIMIT 10
                ''')
                
                results = cursor.fetchall()
                for league, home, away, can_predict in results:
                    status_icon = "✅" if can_predict == 'YES' else "❌"
                    print(f"  {status_icon} {home} vs {away} [{league}] - {can_predict}")
                
                print("="*60)
                
        except sqlite3.Error as e:
            print(f"Error in debug status: {e}")
    
    def __del__(self):
        """Cleanup driver when object is destroyed."""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass

if __name__ == '__main__':
    # Test the enhanced data fetcher
    fetcher = EnhancedDataFetcher()
    
    print("Testing enhanced data fetcher with league name standardization...")
    
    # Test league standardization first
    print("\n1. Testing league name standardization:")
    test_names = ['england', 'England', 'spain virtual', 'Italy', 'Germany Virtual']
    for name in test_names:
        debug_league_mapping(name)
        print("-" * 30)
    
    print("\n2. Testing completed matches API fetch...")
    api_success = fetcher.run_completed_update()
    
    print("\n3. Testing scheduled matches Selenium fetch...")
    scheduled_success = fetcher.run_scheduled_update()
    
    # Debug database status
    fetcher.debug_database_status()
    
    if api_success and scheduled_success:
        print("\nAll tests completed successfully!")
        print("League names should now be standardized across all tables.")
    else:
        print(f"\nTests completed with issues: API={api_success}, Scheduled={scheduled_success}")
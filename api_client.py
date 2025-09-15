import requests
import json
import time
from datetime import datetime, timedelta
import sqlite3
import os
from typing import Dict, List, Optional
import logging
# Add this import to your api_client.py
from config import standardize_league_name

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VirtualFootballAPI:
    """API client for SportyBet Virtual Football data"""
    
    def __init__(self):
        self.base_url = "https://www.sportybet.com/api/ng/factsCenter/eventResultList"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.existing_matches = set()  # Store unique match keys for duplicate detection
        
        # League mappings based on your APIs
        self.leagues = {
            'england': 'sv:category:202120001',
            'spain': 'sv:category:202120002', 
            'italy': 'sv:category:202120003',
            'germany': 'sv:category:202120004',
            'france': 'sv:category:202120005'
        }
        
        self.sport_id = 'sr:sport:202120001'  # Virtual Football
        
    def get_time_range(self, days_back: int = 0) -> tuple:
        """Get time range for API calls - default to today only"""
        if days_back == 0:
            # Get today's matches only
            now = datetime.now()
            start_time = datetime(now.year, now.month, now.day, 0, 0, 0)  # Start of today
            end_time = datetime(now.year, now.month, now.day, 23, 59, 59)  # End of today
        else:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
        
        # Convert to milliseconds timestamp
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        current_ms = int(time.time() * 1000)
        
        return start_ms, end_ms, current_ms
    
    def fetch_league_matches(self, league_name: str, days_back: int = 0, 
                           page_num: int = 1, page_size: int = 100) -> Optional[Dict]:
        """Fetch matches for a specific league and page"""
        if league_name.lower() not in self.leagues:
            logger.error(f"Unknown league: {league_name}")
            return None
            
        category_id = self.leagues[league_name.lower()]
        start_time, end_time, current_time = self.get_time_range(days_back)
        
        params = {
            'pageNum': page_num,
            'pageSize': page_size,
            'sportId': self.sport_id,
            'categoryId': category_id,
            'startTime': start_time,
            'endTime': end_time,
            '_t': current_time
        }
        
        try:
            logger.info(f"Fetching {league_name} matches (page {page_num})...")
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('bizCode') == 10000:
                logger.info(f"Successfully fetched {league_name} page {page_num}")
                return data
            else:
                logger.error(f"API error for {league_name} page {page_num}: {data.get('message', 'Unknown error')}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Network error fetching {league_name} page {page_num}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {league_name} page {page_num}: {e}")
            return None
    
    def fetch_all_league_pages(self, league_name: str, days_back: int = 0, 
                              page_size: int = 100) -> List[Dict]:
        """Fetch all pages for a specific league with duplicate detection"""
        all_matches = []
        page_num = 1
        total_processed = 0
        existing_matches = set()  # Track unique matches in this fetch
        
        while True:
            logger.info(f"Fetching {league_name} - Page {page_num}")
            data = self.fetch_league_matches(league_name, days_back, page_num, page_size)
            
            if not data:
                logger.warning(f"No data returned for {league_name} page {page_num}")
                break
            
            # Check if we have tournaments with events
            tournaments = data.get('data', {}).get('tournaments', [])
            if not tournaments:
                logger.info(f"No tournaments found in {league_name} page {page_num}")
                break
            
            # Process matches and count new ones
            page_matches = 0
            new_matches = 0
            for tournament in tournaments:
                events = tournament.get('events', [])
                for event in events:
                    match_key = f"{event.get('eventId', '')}_{event.get('estimateStartTime', '')}"
                    if match_key in existing_matches:
                        continue  # Skip duplicates
                    existing_matches.add(match_key)
                    page_matches += 1
                    new_matches += 1
            
            if new_matches == 0:
                logger.info(f"No new matches found in {league_name} page {page_num}")
                break
            
            all_matches.append(data)
            logger.info(f"Found {page_matches} matches ({new_matches} new) in {league_name} page {page_num}")
            total_processed += new_matches
            
            # Check totalNum if available
            total_available = data.get('data', {}).get('totalNum', float('inf'))
            logger.info(f"Total processed: {total_processed}/{total_available}")
            
            if total_processed >= total_available:
                logger.info(f"Reached total available matches for {league_name}")
                break
            
            page_num += 1
            time.sleep(0.5)  # Small delay between requests
        
        logger.info(f"Fetched {len(all_matches)} pages for {league_name}, total {total_processed} matches")
        return all_matches
    
    def fetch_all_leagues(self, days_back: int = 0) -> Dict[str, List[Dict]]:
        """Fetch data from all available leagues with full pagination"""
        all_data = {}
        
        for league_name in self.leagues.keys():
            logger.info(f"\n🏆 Starting to fetch {league_name.title()} League...")
            league_pages = self.fetch_all_league_pages(league_name, days_back)
            
            if league_pages:
                all_data[league_name] = league_pages
                total_matches = 0
                for page_data in league_pages:
                    tournaments = page_data.get('data', {}).get('tournaments', [])
                    for tournament in tournaments:
                        total_matches += len(tournament.get('events', []))
                logger.info(f"✅ {league_name.title()}: {len(league_pages)} pages, {total_matches} total matches")
            else:
                logger.warning(f"❌ No data found for {league_name}")
            
            time.sleep(1)  # Rate limiting between leagues
            
        return all_data

class DataProcessor:
    """Process and structure match data"""
    
    @staticmethod
    def extract_match_info(event: Dict) -> Dict:
        """Extract relevant information from a match event"""
        try:
            # Validate essential fields
            if not event.get('homeTeamName') or not event.get('awayTeamName') or 'setScore' not in event:
                logger.warning(f"Skipping invalid match: {event.get('eventId', 'unknown')} - Missing required fields")
                return {}
            
            # Parse scores
            set_score = event.get('setScore', '0:0').split(':')
            home_score = int(set_score[0]) if len(set_score) >= 2 else 0
            away_score = int(set_score[1]) if len(set_score) >= 2 else 0
            
            # Parse half-time scores if available
            game_scores = event.get('gameScore', ['0:0'])
            half_time_score = game_scores[0] if len(game_scores) > 0 else '0:0'
            ht_parts = half_time_score.split(':')
            ht_home = int(ht_parts[0]) if len(ht_parts) >= 2 else 0
            ht_away = int(ht_parts[1]) if len(ht_parts) >= 2 else 0
            
            match_info = {
                'event_id': event.get('eventId', ''),
                'game_id': event.get('gameId', ''),
                'home_team': event.get('homeTeamName', ''),
                'away_team': event.get('awayTeamName', ''),
                'home_score': home_score,
                'away_score': away_score,
                'total_goals': home_score + away_score,
                'ht_home_score': ht_home,
                'ht_away_score': ht_away,
                'ht_total_goals': ht_home + ht_away,
                'start_time': event.get('estimateStartTime', 0),
                'match_status': event.get('matchStatus', 'Unknown'),
                'league': standardize_league_name(event.get('sport', {}).get('category', {}).get('name', 'Unknown')),
                'result': DataProcessor._get_match_result(home_score, away_score),
                'over_under_2_5': 'Over' if (home_score + away_score) > 2.5 else 'Under',
                'both_teams_scored': 'Yes' if (home_score > 0 and away_score > 0) else 'No'
            }
            
            logger.debug(f"Processed match: {match_info['home_team']} vs {match_info['away_team']} ({match_info['home_score']}:{match_info['away_score']})")
            return match_info
        except Exception as e:
            logger.error(f"Error extracting match info for event {event.get('eventId', 'unknown')}: {e}")
            return {}
    
    @staticmethod
    def _get_match_result(home_score: int, away_score: int) -> str:
        """Determine match result (1/X/2)"""
        if home_score > away_score:
            return '1'  # Home win
        elif away_score > home_score:
            return '2'  # Away win
        else:
            return 'X'  # Draw
    
    @staticmethod
    def process_league_pages(league_pages: List[Dict]) -> List[Dict]:
        """Process all pages of matches for a league"""
        all_matches = []
        
        try:
            for page_data in league_pages:
                tournaments = page_data.get('data', {}).get('tournaments', [])
                
                for tournament in tournaments:
                    events = tournament.get('events', [])
                    
                    for event in events:
                        match_info = DataProcessor.extract_match_info(event)
                        if match_info:
                            all_matches.append(match_info)
                            
        except Exception as e:
            logger.error(f"Error processing league pages: {e}")
            
        return all_matches
    # Then update your DataProcessor.extract_match_info method:
    @staticmethod
    def extract_match_info(event: Dict) -> Dict:
        """Extract relevant information from a match event"""
        try:
            # Validate essential fields
            if not event.get('homeTeamName') or not event.get('awayTeamName') or 'setScore' not in event:
                logger.warning(f"Skipping invalid match: {event.get('eventId', 'unknown')} - Missing required fields")
                return {}
            
            # Parse scores
            set_score = event.get('setScore', '0:0').split(':')
            home_score = int(set_score[0]) if len(set_score) >= 2 else 0
            away_score = int(set_score[1]) if len(set_score) >= 2 else 0
            
            # Parse half-time scores if available
            game_scores = event.get('gameScore', ['0:0'])
            half_time_score = game_scores[0] if len(game_scores) > 0 else '0:0'
            ht_parts = half_time_score.split(':')
            ht_home = int(ht_parts[0]) if len(ht_parts) >= 2 else 0
            ht_away = int(ht_parts[1]) if len(ht_parts) >= 2 else 0
            
            # Get raw league name and standardize it
            raw_league_name = event.get('sport', {}).get('category', {}).get('name', 'Unknown')
            standardized_league_name = standardize_league_name(raw_league_name)
            
            match_info = {
                'event_id': event.get('eventId', ''),
                'game_id': event.get('gameId', ''),
                'home_team': event.get('homeTeamName', ''),
                'away_team': event.get('awayTeamName', ''),
                'home_score': home_score,
                'away_score': away_score,
                'total_goals': home_score + away_score,
                'ht_home_score': ht_home,
                'ht_away_score': ht_away,
                'ht_total_goals': ht_home + ht_away,
                'start_time': event.get('estimateStartTime', 0),
                'match_status': event.get('matchStatus', 'Unknown'),
                'league': standardized_league_name,  # Now uses standardized name
                'result': DataProcessor._get_match_result(home_score, away_score),
                'over_under_2_5': 'Over' if (home_score + away_score) > 2.5 else 'Under',
                'both_teams_scored': 'Yes' if (home_score > 0 and away_score > 0) else 'No'
            }
            
            logger.debug(f"Processed match: {match_info['home_team']} vs {match_info['away_team']} ({match_info['home_score']}:{match_info['away_score']}) - {standardized_league_name}")
            return match_info
        except Exception as e:
            logger.error(f"Error extracting match info for event {event.get('eventId', 'unknown')}: {e}")
            return {}

class LeagueTableGenerator:
    """Generate league tables from match data - FIXED VERSION"""
    
    def __init__(self, expected_teams: List[str] = None):
        self.team_stats = {}
        # Don't use expected_teams for initialization - only use actual match data
        self.expected_teams = expected_teams or []
    
    def add_match(self, match: Dict):
        """Add a match result to team statistics"""
        home_team = match['home_team']
        away_team = match['away_team']
        
        if not home_team or not away_team:
            logger.warning(f"Skipping match with missing teams: {match.get('event_id', 'unknown')}")
            return
        
        home_score = match['home_score']
        away_score = match['away_score']
        
        # Initialize teams ONLY when they appear in actual matches
        for team in [home_team, away_team]:
            if team not in self.team_stats:
                self.team_stats[team] = {
                    'team_name': team,
                    'matches_played': 0,
                    'wins': 0,
                    'draws': 0,
                    'losses': 0,
                    'goals_for': 0,
                    'goals_against': 0,
                    'goal_difference': 0,
                    'points': 0,
                    'home_matches': 0,
                    'away_matches': 0,
                    'last_5_results': []
                }
        
        # Update home team stats
        home_stats = self.team_stats[home_team]
        home_stats['matches_played'] += 1
        home_stats['home_matches'] += 1
        home_stats['goals_for'] += home_score
        home_stats['goals_against'] += away_score
        
        # Update away team stats
        away_stats = self.team_stats[away_team]
        away_stats['matches_played'] += 1
        away_stats['away_matches'] += 1
        away_stats['goals_for'] += away_score
        away_stats['goals_against'] += home_score
        
        # Determine result and update accordingly
        if home_score > away_score:  # Home win
            home_stats['wins'] += 1
            home_stats['points'] += 3
            away_stats['losses'] += 1
            home_stats['last_5_results'].append('W')
            away_stats['last_5_results'].append('L')
        elif away_score > home_score:  # Away win
            away_stats['wins'] += 1
            away_stats['points'] += 3
            home_stats['losses'] += 1
            home_stats['last_5_results'].append('L')
            away_stats['last_5_results'].append('W')
        else:  # Draw
            home_stats['draws'] += 1
            home_stats['points'] += 1
            away_stats['draws'] += 1
            away_stats['points'] += 1
            home_stats['last_5_results'].append('D')
            away_stats['last_5_results'].append('D')
        
        # Keep only last 5 results
        for team_stats in [home_stats, away_stats]:
            if len(team_stats['last_5_results']) > 5:
                team_stats['last_5_results'] = team_stats['last_5_results'][-5:]
    
    def generate_table(self) -> List[Dict]:
        """Generate sorted league table from ACTUAL match data only"""
        
        # Calculate goal difference for each team
        for team_name, stats in self.team_stats.items():
            stats['goal_difference'] = stats['goals_for'] - stats['goals_against']
        
        # Sort teams by points (desc), then goal difference (desc), then goals for (desc)
        sorted_teams = sorted(
            self.team_stats.values(),
            key=lambda x: (x['points'], x['goal_difference'], x['goals_for']),
            reverse=True
        )
        
        # Add position
        for i, team in enumerate(sorted_teams, 1):
            team['position'] = i
            
        # Log the final table for debugging
        logger.info(f"Generated table with {len(sorted_teams)} teams")
        match_counts = [team['matches_played'] for team in sorted_teams]
        if match_counts:
            logger.info(f"Match count range: {min(match_counts)} - {max(match_counts)}")
            
        return sorted_teams


class DatabaseManager:
    """Manage SQLite database for storing match data and league tables"""
    
    def __init__(self, db_path: str = 'virtual_football.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Matches table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    game_id TEXT,
                    home_team TEXT,
                    away_team TEXT,
                    home_score INTEGER,
                    away_score INTEGER,
                    total_goals INTEGER,
                    ht_home_score INTEGER,
                    ht_away_score INTEGER,
                    ht_total_goals INTEGER,
                    start_time INTEGER,
                    match_status TEXT,
                    league TEXT,
                    result TEXT,
                    over_under_2_5 TEXT,
                    both_teams_scored TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # League tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS league_tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_name TEXT,
                    team_name TEXT,
                    position INTEGER,
                    matches_played INTEGER,
                    wins INTEGER,
                    draws INTEGER,
                    losses INTEGER,
                    goals_for INTEGER,
                    goals_against INTEGER,
                    goal_difference INTEGER,
                    points INTEGER,
                    last_5_results TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(league_name, team_name)
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def save_matches(self, matches: List[Dict], league_name: str):
        """Save matches to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            saved_count = 0
            for match in matches:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO matches 
                        (event_id, game_id, home_team, away_team, home_score, away_score,
                         total_goals, ht_home_score, ht_away_score, ht_total_goals,
                         start_time, match_status, league, result, over_under_2_5, both_teams_scored)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        match['event_id'], match['game_id'], match['home_team'], 
                        match['away_team'], match['home_score'], match['away_score'],
                        match['total_goals'], match['ht_home_score'], match['ht_away_score'],
                        match['ht_total_goals'], match['start_time'], match['match_status'],
                        league_name, match['result'], match['over_under_2_5'], match['both_teams_scored']
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving match {match.get('event_id', 'unknown')}: {e}")
            
            conn.commit()
            logger.info(f"Saved {saved_count}/{len(matches)} matches for {league_name}")
    
    def save_league_table(self, table: List[Dict], league_name: str):
        """Save league table to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear existing table for this league
            cursor.execute('DELETE FROM league_tables WHERE league_name = ?', (league_name,))
            
            for team in table:
                try:
                    cursor.execute('''
                        INSERT INTO league_tables 
                        (league_name, team_name, position, matches_played, wins, draws, losses,
                         goals_for, goals_against, goal_difference, points, last_5_results)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        league_name, team['team_name'], team['position'], team['matches_played'],
                        team['wins'], team['draws'], team['losses'], team['goals_for'],
                        team['goals_against'], team['goal_difference'], team['points'],
                        ','.join(team['last_5_results'])
                    ))
                except Exception as e:
                    logger.error(f"Error saving team {team.get('team_name', 'unknown')}: {e}")
            
            conn.commit()
            logger.info(f"Saved league table for {league_name}")
    
    def get_team_last_5_matches(self, team_name: str, league_name: str) -> List[Dict]:
        """Get last 5 matches for a team"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM matches 
                WHERE (home_team = ? OR away_team = ?) AND league = ?
                ORDER BY start_time DESC 
                LIMIT 5
            ''', (team_name, team_name, league_name))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_head_to_head(self, team1: str, team2: str, league_name: str, limit: int = 10) -> List[Dict]:
        """Get head-to-head matches between two teams"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM matches 
                WHERE ((home_team = ? AND away_team = ?) OR (home_team = ? AND away_team = ?))
                AND league = ?
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (team1, team2, team2, team1, league_name, limit))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main():
    """Main function to fetch and process data"""
    print("🚀 Virtual Football Data Fetcher - Enhanced with Full Pagination")
    print("=" * 60)
    print(f"📅 Fetching TODAY'S matches with complete pagination ({datetime.now().strftime('%Y-%m-%d')})")
    
    # Initialize components
    api_client = VirtualFootballAPI()
    data_processor = DataProcessor()
    db_manager = DatabaseManager()
    
    # Fetch data from all leagues (today only, all pages)
    print("📡 Fetching data from all leagues (all pages)...")
    all_league_data = api_client.fetch_all_leagues(days_back=0)  # Today only
    
    if not all_league_data:
        print("❌ No data fetched. Check API connectivity.")
        return
    
    print(f"\n✅ Successfully fetched data from {len(all_league_data)} leagues")
    
    total_matches_all_leagues = 0
    
    # Process each league
    for league_name, league_pages in all_league_data.items():
        print(f"\n🏆 Processing {league_name.title()} League...")
        
        matches = data_processor.process_league_pages(league_pages)
        
        if not matches:
            print(f"   ⚠️  No matches found for {league_name}")
            continue
        
        # Save matches to database
        db_manager.save_matches(matches, league_name)
        
        # Generate league table WITHOUT expected teams
        table_generator = LeagueTableGenerator()  # NO expected_teams parameter
        
        for match in matches:
            table_generator.add_match(match)
        
        league_table = table_generator.generate_table()
        db_manager.save_league_table(league_table, league_name)
        
        # Validate and report
        if league_table:
            match_counts = [team['matches_played'] for team in league_table]
            print(f"   📊 Teams: {len(league_table)}, Match range: {min(match_counts)}-{max(match_counts)}")
            total_matches_all_leagues += sum(match_counts) / 2  # Each match counts for two teams
        else:
            print(f"   ❌ No league table generated for {league_name}")
        
        # Display all teams
        print("   📋 League Table:")
        for i, team in enumerate(league_table, 1):
            last_5 = ','.join(team['last_5_results'][-5:])
            print(f"      {i}. {team['team_name']} - {team['points']} pts "
                  f"({team['matches_played']} matches, {team['wins']}W-{team['draws']}D-{team['losses']}L) "
                  f"[Last 5: {last_5}]")
    
    print(f"\n🎉 SUMMARY:")
    print(f"   📊 Total matches processed: {int(total_matches_all_leagues)}")
    print(f"   🏆 Leagues processed: {len(all_league_data)}")
    print(f"   💾 Database: 'virtual_football.db'")
    print(f"\n✅ Enhanced Phase 1 Complete with Full Pagination!")
    print("📝 Next: Run the test script to verify everything works")


if __name__ == "__main__":
    main()
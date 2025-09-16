from flask import Flask, jsonify, render_template
from predictor import Predictor
import sqlite3
from config import standardize_league_name, get_display_name
import sqlite3
import os 

def get_db_path():
    """Get the correct database path based on environment."""
    # Check if we're on Vercel or other cloud platform where current dir isn't writable
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV') or not os.access('.', os.W_OK):
        # Use /tmp directory on Vercel (writable)
        return '/tmp/virtual_football.db'
    else:
        # Use current directory for local development
        return 'virtual_football.db'

app = Flask(__name__, template_folder='templates', static_folder='static')
db_path = get_db_path()
predictor = Predictor(db_path)

# Initialize database tables on startup
def init_database():
    """Initialize database tables if they don't exist."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create matches table
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
            
            # Create league tables
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
            
            # Create scheduled matches table
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
            print(f"Database initialized successfully at: {db_path}")
            
            # Add some sample data if tables are empty (for demo purposes)
            cursor.execute('SELECT COUNT(*) FROM matches')
            if cursor.fetchone()[0] == 0:
                print("Adding sample data for demo...")
                sample_matches = [
                    ('match1', 'game1', 'ARS', 'LEE', 2, 1, 3, 1, 0, 1, 1640995200000, 'FT', 'england virtual', '1', 'Over', 'No'),
                    ('match2', 'game2', 'LEE', 'CHE', 1, 2, 3, 0, 1, 1, 1641081600000, 'FT', 'england virtual', '2', 'Over', 'Yes'),
                    ('match3', 'game3', 'CHE', 'MCI', 0, 3, 3, 0, 2, 2, 1641168000000, 'FT', 'england virtual', '2', 'Over', 'No'),
                    ('match4', 'game4', 'MCI', 'ARS', 2, 2, 4, 1, 1, 2, 1641254400000, 'FT', 'england virtual', 'X', 'Over', 'Yes'),
                ]
                
                cursor.executemany('''
                    INSERT INTO matches 
                    (event_id, game_id, home_team, away_team, home_score, away_score, total_goals, 
                     ht_home_score, ht_away_score, ht_total_goals, start_time, match_status, 
                     league, result, over_under_2_5, both_teams_scored)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_matches)
                
                # Add sample scheduled matches
                import time
                current_time = int(time.time() * 1000)
                future_time = current_time + (60 * 60 * 1000)  # 1 hour from now
                
                sample_scheduled = [
                    ('sched1', 'ARS', 'MCI', 'england virtual', future_time, '15:30', 'scheduled', 2.1, 3.2, 3.4),
                    ('sched2', 'LEE', 'CHE', 'england virtual', future_time + 1800000, '16:00', 'scheduled', 2.8, 3.0, 2.6),
                ]
                
                cursor.executemany('''
                    INSERT INTO scheduled_matches 
                    (event_id, home_team, away_team, league, start_time, match_time_display, status, home_odds, draw_odds, away_odds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_scheduled)
                
                conn.commit()
                print("Sample data added successfully")
                
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")

# Initialize database on startup
init_database()

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/leagues', methods=['GET'])
def get_leagues():
    """Return list of available leagues from both completed and scheduled matches."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Get leagues from both completed matches and scheduled matches
            cursor.execute('''
                SELECT DISTINCT league FROM matches
                UNION
                SELECT DISTINCT league FROM scheduled_matches
                ORDER BY league
            ''')
            raw_leagues = [row[0] for row in cursor.fetchall() if row[0]]
            
            # Standardize and create league objects with display names
            leagues = []
            seen_leagues = set()
            
            for raw_league in raw_leagues:
                standardized = standardize_league_name(raw_league)
                if standardized not in seen_leagues:
                    seen_leagues.add(standardized)
                    leagues.append({
                        'value': standardized,
                        'display': get_display_name(standardized),
                        'raw': raw_league  # For debugging
                    })
            
            # Sort by display name
            leagues.sort(key=lambda x: x['display'])
            
        return jsonify({
            'leagues': leagues,
            'count': len(leagues)
        })
    except sqlite3.Error as e:
        return jsonify({'error': f'DB Error: {e}'}), 500

@app.route('/matches/<league>', methods=['GET'])
def get_matches(league):
    """Return SCHEDULED matches for a specific league for predictions."""
    try:
        # Standardize the incoming league name
        standardized_league = standardize_league_name(league)
        display_league = get_display_name(standardized_league)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # FIXED: Simplified can_predict logic
            cursor.execute('''
                SELECT DISTINCT s.home_team, s.away_team, s.match_time_display, s.status, s.event_id
                FROM scheduled_matches s
                WHERE s.league = ? AND s.status = 'scheduled'
                ORDER BY s.home_team, s.away_team
                LIMIT 50
            ''', (standardized_league,))
            
            matches = []
            for row in cursor.fetchall():
                home_team, away_team, match_time_display, status, event_id = row
                
                # Check if we have historical data for these specific teams
                cursor.execute('''
                    SELECT COUNT(*) FROM matches 
                    WHERE league = ? AND (
                        (home_team = ? OR away_team = ?) OR
                        (home_team = ? OR away_team = ?)
                    )
                ''', (standardized_league, home_team, home_team, away_team, away_team))
                
                historical_count = cursor.fetchone()[0]
                can_predict = historical_count >= 2  # Need at least 2 historical matches combined
                
                print(f"Match: {home_team} vs {away_team} - Historical matches: {historical_count} - Can predict: {can_predict}")
                
                matches.append({
                    'home_team': home_team, 
                    'away_team': away_team,
                    'match_time': match_time_display or 'TBD',
                    'status': status,
                    'event_id': event_id,
                    'type': 'scheduled',
                    'can_predict': can_predict,
                    'prediction_note': 'Prediction available' if can_predict else 'Insufficient historical data'
                })
            
            # If no scheduled matches, fall back to recent completed matches for demonstration
            if not matches:
                cursor.execute('''
                    SELECT DISTINCT home_team, away_team, event_id
                    FROM matches 
                    WHERE league = ? 
                    ORDER BY start_time DESC 
                    LIMIT 20
                ''', (standardized_league,))
                
                for row in cursor.fetchall():
                    matches.append({
                        'home_team': row[0], 
                        'away_team': row[1],
                        'event_id': row[2],
                        'match_time': 'Completed',
                        'status': 'completed',
                        'type': 'historical',
                        'can_predict': True,  # Historical matches always allow prediction
                        'prediction_note': 'Historical analysis available'
                    })
        
        print(f"Returning {len(matches)} matches for {standardized_league}")
        return jsonify({
            'matches': matches,
            'league_display': display_league,
            'league_standardized': standardized_league
        })
    except sqlite3.Error as e:
        print(f"DB Error in get_matches: {e}")
        return jsonify({'error': f'DB Error: {e}'}), 500

@app.route('/predict/<league>/<home_team>/<away_team>', methods=['GET'])
def predict_match(league, home_team, away_team):
    """Return prediction for a specific match."""
    print(f"Flask received: {home_team} vs {away_team} in {league}")
    print(f"Calling predictor.predict_match...")
    
    try:
        # Standardize league name for consistent lookups
        standardized_league = standardize_league_name(league)
        print(f"Standardized league: {standardized_league}")
        
        prediction = predictor.predict_match(home_team, away_team, standardized_league)
        
        if prediction:
            print("Prediction generated successfully!")
            return jsonify({
                'prediction': {
                    'home_team': prediction['home_team'],
                    'away_team': prediction['away_team'],
                    'league': prediction['league'],
                    'league_display': get_display_name(prediction['league']),
                    'predicted_result': prediction['predicted_result'],
                    'predicted_score': prediction['predicted_score'],
                    'home_win_prob': prediction['home_win_prob'],
                    'draw_prob': prediction['draw_prob'],
                    'away_win_prob': prediction['away_win_prob'],
                    'btts': prediction['btts'],
                    'over_2_5': prediction['over_2_5'],
                    'formatted': predictor.format_prediction(prediction)
                }
            })
        else:
            print("No prediction generated - predictor returned None")
            return jsonify({'error': 'Prediction unavailable - insufficient historical data'}), 400
            
    except Exception as e:
        print(f"Error in predict_match: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Prediction error: {str(e)}'}), 500

@app.route('/league_table/<league>', methods=['GET'])
def get_league_table(league):
    """Return league table for a specific league."""
    try:
        # Standardize league name for consistent lookups
        standardized_league = standardize_league_name(league)
        display_league = get_display_name(standardized_league)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT team_name, position, matches_played, wins, draws, losses, 
                       goals_for, goals_against, goal_difference, points, last_5_results
                FROM league_tables 
                WHERE league_name = ? 
                ORDER BY position
            ''', (standardized_league,))
            
            table = []
            for row in cursor.fetchall():
                team_data = {
                    'team_name': row[0],
                    'position': row[1],
                    'matches_played': row[2],
                    'wins': row[3],
                    'draws': row[4],
                    'losses': row[5],
                    'goals_for': row[6],
                    'goals_against': row[7],
                    'goal_difference': row[8],
                    'points': row[9],
                    'last_5_results': row[10] or '',
                    # Add aliases for common field name variations
                    'MP': row[2],
                    'W': row[3],
                    'D': row[4],
                    'L': row[5],
                    'GF': row[6],
                    'GA': row[7],
                    'GD': row[8],
                    'Pts': row[9]
                }
                table.append(team_data)
            
            return jsonify({
                'league_table': table,
                'league_display': display_league,
                'league_standardized': standardized_league
            })
            
    except sqlite3.Error as e:
        return jsonify({'error': f'DB Error: {e}'}), 500

@app.route('/debug/database', methods=['GET'])
def debug_database():
    """Debug endpoint to check what's in the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check scheduled matches
            cursor.execute('SELECT COUNT(*) FROM scheduled_matches')
            scheduled_count = cursor.fetchone()[0]
            
            # Check completed matches  
            cursor.execute('SELECT COUNT(*) FROM matches')
            completed_count = cursor.fetchone()[0]
            
            # Check league tables
            cursor.execute('SELECT COUNT(*) FROM league_tables')
            table_count = cursor.fetchone()[0]
            
            # Get league distribution
            league_info = {}
            
            # From scheduled matches
            cursor.execute('SELECT league, COUNT(*) FROM scheduled_matches GROUP BY league')
            scheduled_leagues = cursor.fetchall()
            
            # From completed matches
            cursor.execute('SELECT league, COUNT(*) FROM matches GROUP BY league')  
            completed_leagues = cursor.fetchall()
            
            # From league tables
            cursor.execute('SELECT league_name, COUNT(*) FROM league_tables GROUP BY league_name')
            table_leagues = cursor.fetchall()
            
            # Create standardized league info
            all_raw_leagues = set()
            for leagues_list in [scheduled_leagues, completed_leagues, table_leagues]:
                for league, count in leagues_list:
                    all_raw_leagues.add(league)
            
            standardized_leagues = []
            for raw_league in all_raw_leagues:
                standardized = standardize_league_name(raw_league)
                display = get_display_name(standardized)
                standardized_leagues.append({
                    'raw': raw_league,
                    'standardized': standardized, 
                    'display': display
                })
            
            # Get sample data
            cursor.execute('SELECT home_team, away_team, league, status FROM scheduled_matches LIMIT 5')
            scheduled_sample = cursor.fetchall()
            
            cursor.execute('SELECT home_team, away_team, league, home_score, away_score FROM matches LIMIT 5')
            completed_sample = cursor.fetchall()
            
            # Check prediction capability
            cursor.execute('''
                SELECT s.league, COUNT(*) as scheduled_count,
                       SUM(CASE WHEN EXISTS (
                           SELECT 1 FROM matches m 
                           WHERE m.league = s.league 
                           AND (m.home_team = s.home_team OR m.away_team = s.home_team)
                           AND (m.home_team = s.away_team OR m.away_team = s.away_team)
                       ) THEN 1 ELSE 0 END) as predictable_count
                FROM scheduled_matches s
                GROUP BY s.league
            ''')
            prediction_stats = cursor.fetchall()
            
            return jsonify({
                'database_status': {
                    'database_path': db_path,
                    'scheduled_matches_count': scheduled_count,
                    'completed_matches_count': completed_count,
                    'league_tables_count': table_count,
                    'scheduled_sample': scheduled_sample,
                    'completed_sample': completed_sample,
                    'standardized_leagues': standardized_leagues,
                    'prediction_stats': prediction_stats,
                    'scheduled_by_league': scheduled_leagues,
                    'completed_by_league': completed_leagues,
                    'tables_by_league': table_leagues
                }
            })
            
    except sqlite3.Error as e:
        return jsonify({'error': f'DB Error: {e}'}), 500

@app.route('/debug')
def debug_info():
    try:
        current_dir = os.getcwd()
        files = os.listdir('.')
        db_exists = os.path.exists(db_path)
        is_writable = os.access('.', os.W_OK)
        
        return f"""
        <h2>Debug Info</h2>
        <p><strong>Current directory:</strong> {current_dir}</p>
        <p><strong>Directory writable:</strong> {is_writable}</p>
        <p><strong>Database path:</strong> {db_path}</p>
        <p><strong>Database file exists:</strong> {db_exists}</p>
        <p><strong>Files in directory:</strong> {files}</p>
        <p><strong>Environment variables:</strong> VERCEL={os.environ.get('VERCEL')}, VERCEL_ENV={os.environ.get('VERCEL_ENV')}</p>
        """
    except Exception as e:
        return f"Debug error: {e}"

@app.route('/debug/test-api')
def test_api():
    """Test if the SportyBet API is accessible"""
    try:
        import requests
        
        # Test the actual API endpoint your code uses
        url = "https://www.sportybet.com/api/ng/factsCenter/eventResultList"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        params = {
            'pageNum': 1,
            'pageSize': 10,
            'sportId': 'sr:sport:202120001',
            'categoryId': 'sv:category:202120001',  # England
            'startTime': int(time.time() * 1000) - (24 * 60 * 60 * 1000),  # 24 hours ago
            'endTime': int(time.time() * 1000),
            '_t': int(time.time() * 1000)
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        return jsonify({
            'status_code': response.status_code,
            'accessible': response.status_code == 200,
            'response_preview': str(response.text)[:500] if response.text else 'No content',
            'url_used': response.url
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'accessible': False
        })

@app.route('/debug/imports')
def debug_imports():
    """Check if all required modules can be imported"""
    import_status = {}
    
    try:
        from api_client import VirtualFootballAPI, DataProcessor, DatabaseManager
        import_status['api_client'] = 'Success'
    except Exception as e:
        import_status['api_client'] = f'Failed: {str(e)}'
    
    try:
        from config import standardize_league_name
        import_status['config'] = 'Success'
    except Exception as e:
        import_status['config'] = f'Failed: {str(e)}'
    
    try:
        import requests
        import_status['requests'] = 'Success'
    except Exception as e:
        import_status['requests'] = f'Failed: {str(e)}'
    
    return jsonify(import_status)

@app.route('/health')
def health_check():
    """Simple health check endpoint."""
    try:
        # Test database connection
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM matches')
            matches_count = cursor.fetchone()[0]
            
        return jsonify({
            'status': 'healthy',
            'database_path': db_path,
            'matches_count': matches_count
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'database_path': db_path
        }), 500

if __name__ == '__main__':
    print(f"Starting Flask app with database at: {db_path}")
    app.run(debug=True)
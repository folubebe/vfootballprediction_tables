from flask import Flask, jsonify, render_template
from predictor import Predictor
import sqlite3
from config import standardize_league_name, get_display_name
import sqlite3
import os 

app = Flask(__name__, template_folder='templates', static_folder='static')
db_path = 'virtual_football.db'
predictor = Predictor(db_path)

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
        db_exists = os.path.exists('virtual_football.db')
        
        return f"""
        <h2>Debug Info</h2>
        <p><strong>Current directory:</strong> {current_dir}</p>
        <p><strong>Files in directory:</strong> {files}</p>
        <p><strong>Database file exists:</strong> {db_exists}</p>
        """
    except Exception as e:
        return f"Debug error: {e}"

@app.route('/debug-db')
def debug_database_creation():
    import os
    import sqlite3
    
    try:
        # Try to create database in current directory
        db_path = 'virtual_football.db'
        
        # Try to connect and create tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create a simple test table
        cursor.execute('CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)')
        cursor.execute('INSERT INTO test_table (id, name) VALUES (1, "test")')
        conn.commit()
        
        # Check if it worked
        cursor.execute('SELECT * FROM test_table')
        result = cursor.fetchone()
        conn.close()
        
        # Check if file was created
        db_exists_now = os.path.exists(db_path)
        
        return f"""
        <h2>Database Creation Test</h2>
        <p><strong>Database created:</strong> {db_exists_now}</p>
        <p><strong>Test data inserted:</strong> {result}</p>
        <p><strong>Current directory writable:</strong> True</p>
        """
        
    except Exception as e:
        return f"""
        <h2>Database Creation Test</h2>
        <p><strong>Error:</strong> {str(e)}</p>
        <p><strong>This means:</strong> Current directory is not writable</p>
        """



if __name__ == '__main__':
    print("Starting Flask app with league name standardization...")
    app.run(debug=True)
import sqlite3
from datetime import datetime
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

class Predictor:
    def __init__(self, db_path=None):
        self.db_path = db_path or get_db_path()

    def get_team_stats(self, team_name, league, limit=5):
        """Get team stats with proper connection handling"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                print(f"Looking for team: {team_name} in league: {league}")
                
                cursor.execute('''
                    SELECT home_team, away_team, home_score, away_score, 
                           over_under_2_5, both_teams_scored, result
                    FROM matches 
                    WHERE (home_team = ? OR away_team = ?) AND league = ?
                    ORDER BY start_time DESC 
                    LIMIT ?
                ''', (team_name, team_name, league, limit))
                
                matches = cursor.fetchall()
                print(f"Found {len(matches)} matches for {team_name}")
                
                if not matches:
                    return None
                
                # Process matches
                wins = draws = losses = goals_for = goals_against = btts_yes = over_2_5 = 0
                
                for match in matches:
                    home_team, away_team, home_score, away_score, ou, btts, result = match
                    is_home = (team_name == home_team)
                    
                    # Goals
                    goals_for += home_score if is_home else away_score
                    goals_against += away_score if is_home else home_score
                    
                    # Results
                    if result == '1' and is_home:
                        wins += 1
                    elif result == '2' and not is_home:
                        wins += 1
                    elif result == 'X':
                        draws += 1
                    else:
                        losses += 1
                    
                    # BTTS and Over/Under
                    if btts and btts.lower() == 'yes':
                        btts_yes += 1
                    if ou and ou.lower() == 'over':
                        over_2_5 += 1
                
                stats = {
                    'matches': len(matches),
                    'wins': wins,
                    'draws': draws,
                    'losses': losses,
                    'goals_for': goals_for,
                    'goals_against': goals_against,
                    'btts_yes': btts_yes,
                    'over_2_5': over_2_5
                }
                
                print(f"Stats for {team_name}: {stats}")
                return stats
                
        except sqlite3.Error as e:
            print(f"Database error getting team stats for {team_name}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting team stats for {team_name}: {e}")
            return None

    def get_h2h_stats(self, home_team, away_team, league, limit=5):
        """Get head-to-head stats with proper error handling"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT home_team, away_team, result
                    FROM matches 
                    WHERE ((home_team = ? AND away_team = ?) OR (home_team = ? AND away_team = ?)) 
                    AND league = ?
                    ORDER BY start_time DESC 
                    LIMIT ?
                ''', (home_team, away_team, away_team, home_team, league, limit))
                
                matches = cursor.fetchall()
                home_wins = draws = away_wins = 0
                
                for match in matches:
                    match_home, match_away, result = match
                    if result == '1':
                        home_wins += 1
                    elif result == 'X':
                        draws += 1
                    elif result == '2':
                        away_wins += 1
                
                return {
                    'home_wins': home_wins,
                    'draws': draws, 
                    'away_wins': away_wins,
                    'total': len(matches)
                }
                
        except sqlite3.Error as e:
            print(f"Database error getting H2H stats for {home_team} vs {away_team}: {e}")
            return {'home_wins': 0, 'draws': 0, 'away_wins': 0, 'total': 0}
        except Exception as e:
            print(f"Unexpected error getting H2H stats for {home_team} vs {away_team}: {e}")
            return {'home_wins': 0, 'draws': 0, 'away_wins': 0, 'total': 0}

    def get_match_start_time(self, home_team, away_team, league):
        """Get the actual start time of the match from scheduled_matches table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT start_time, match_time_display
                    FROM scheduled_matches 
                    WHERE home_team = ? AND away_team = ? AND league = ?
                    ORDER BY start_time DESC
                    LIMIT 1
                ''', (home_team, away_team, league))
                
                result = cursor.fetchone()
                if result:
                    start_time_ms, match_time_display = result
                    # Convert from milliseconds to datetime
                    start_time = datetime.fromtimestamp(start_time_ms / 1000)
                    return start_time.strftime('%H:%M'), match_time_display
                else:
                    # If no scheduled match found, return current time as fallback
                    return datetime.now().strftime('%H:%M'), None
                    
        except sqlite3.Error as e:
            print(f"Database error getting match start time: {e}")
            return datetime.now().strftime('%H:%M GMT'), None
        except Exception as e:
            print(f"Unexpected error getting match start time: {e}")
            return datetime.now().strftime('%H:%M GMT'), None

    def predict_match(self, home_team, away_team, league):
        """Generate prediction with comprehensive error handling"""
        print(f"\n=== PREDICTING: {home_team} vs {away_team} [{league}] ===")
        
        try:
            home_stats = self.get_team_stats(home_team, league)
            away_stats = self.get_team_stats(away_team, league)
            h2h_stats = self.get_h2h_stats(home_team, away_team, league)
            
            # Get match start time
            match_start_time, match_time_display = self.get_match_start_time(home_team, away_team, league)
            
            # Check if we got the stats
            if not home_stats:
                print(f"❌ No stats found for {home_team}")
                return None
            if not away_stats:
                print(f"❌ No stats found for {away_team}")
                return None
                
            print(f"✅ Got stats for both teams")
            print(f"Home stats: {home_stats}")
            print(f"Away stats: {away_stats}")
            print(f"H2H stats: {h2h_stats}")
            print(f"Match start time: {match_start_time}")
            
            # Calculate probabilities with safety checks
            home_matches = max(home_stats['matches'], 1)  # Prevent division by zero
            away_matches = max(away_stats['matches'], 1)
            
            home_win_rate = home_stats['wins'] / home_matches
            away_win_rate = away_stats['wins'] / away_matches
            home_draw_rate = home_stats['draws'] / home_matches
            away_draw_rate = away_stats['draws'] / away_matches
            
            # Home advantage
            home_win_prob = home_win_rate * 0.6 + 0.15  # 15% home advantage
            away_win_prob = away_win_rate * 0.6
            draw_prob = (home_draw_rate + away_draw_rate) / 2
            
            # Normalize to ensure probabilities sum to 1
            total = home_win_prob + away_win_prob + draw_prob
            if total > 0:  # Safety check
                home_win_prob /= total
                away_win_prob /= total  
                draw_prob /= total
            else:
                # Fallback if all probabilities are 0
                home_win_prob = away_win_prob = draw_prob = 1/3
            
            # Determine result
            if home_win_prob > away_win_prob and home_win_prob > draw_prob:
                predicted_result = '1'
                predicted_score = '2:1'
            elif away_win_prob > home_win_prob and away_win_prob > draw_prob:
                predicted_result = '2'
                predicted_score = '1:2'
            else:
                predicted_result = 'X'
                predicted_score = '1:1'
            
            # BTTS and Over/Under with safety checks
            total_matches = home_matches + away_matches
            btts_rate = (home_stats['btts_yes'] + away_stats['btts_yes']) / total_matches if total_matches > 0 else 0
            over_rate = (home_stats['over_2_5'] + away_stats['over_2_5']) / total_matches if total_matches > 0 else 0
            
            result = {
                'home_team': home_team,
                'away_team': away_team,
                'league': league,
                'predicted_result': predicted_result,
                'predicted_score': predicted_score,
                'home_win_prob': round(home_win_prob * 100, 1),
                'draw_prob': round(draw_prob * 100, 1),
                'away_win_prob': round(away_win_prob * 100, 1),
                'btts': 'Yes' if btts_rate > 0.5 else 'No',
                'over_2_5': 'Over' if over_rate > 0.5 else 'Under',
                'match_start_time': match_start_time,  # Add this to the result
                'match_time_display': match_time_display,  # Add this too for flexibility
                'home_stats': home_stats,
                'away_stats': away_stats,
                'h2h_stats': h2h_stats
            }
            
            print(f"✅ PREDICTION GENERATED!")
            print(f"Result: {predicted_result} ({predicted_score})")
            print(f"Probabilities: H:{result['home_win_prob']}% D:{result['draw_prob']}% A:{result['away_win_prob']}%")
            
            return result
            
        except Exception as e:
            print(f"Error generating prediction for {home_team} vs {away_team}: {e}")
            return None

    def format_prediction(self, prediction):
        """Format prediction output with error handling and correct match time"""
        try:
            if not prediction:
                return "Prediction unavailable - insufficient historical data."
            
            home_stats = prediction.get('home_stats', {})
            away_stats = prediction.get('away_stats', {})
            
            # Safety checks for missing data
            home_matches = home_stats.get('matches', 0)
            away_matches = away_stats.get('matches', 0)
            
            # Use the actual match start time instead of current time
            match_time = prediction.get('match_start_time', 'TBD')
            
            return f"""Mathematical Prediction Analysis for this {prediction['league']} game:
{prediction['home_team']} meets {prediction['away_team']} in a match in {prediction['league']} at {match_time}.

Statistics predict a full time result of {prediction['predicted_score']}.

{'A Home Win is very likely to happen.' if prediction['predicted_result'] == '1' else 
 'A Draw is very likely to happen.' if prediction['predicted_result'] == 'X' else 
 'An Away Win is very likely to happen.'}

The Analysis suggests {prediction['over_2_5']} 2.5 goals in this match.

And a {prediction['btts']} for both teams to score.

Key Information:
{prediction['home_team']} - Last {home_matches} matches: {home_stats.get('wins', 0)}W {home_stats.get('draws', 0)}D {home_stats.get('losses', 0)}L
{prediction['away_team']} - Last {away_matches} matches: {away_stats.get('wins', 0)}W {away_stats.get('draws', 0)}D {away_stats.get('losses', 0)}L"""

        except Exception as e:
            print(f"Error formatting prediction: {e}")
            return "Error formatting prediction - please try again."

# Test function with improved error handling
def test_prediction():
    """Test the improved predictor"""
    try:
        predictor = Predictor()
        
        # Test with your actual data
        result = predictor.predict_match("ARS", "LEE", "england virtual")
        
        if result:
            print("\n" + "="*50)
            print("🎉 PREDICTION WORKS!")
            print("="*50)
            formatted = predictor.format_prediction(result)
            print(formatted)
            return True
        else:
            print("\n❌ Still not working")
            return False
            
    except Exception as e:
        print(f"Error in test_prediction: {e}")
        return False

if __name__ == "__main__":
    test_prediction()
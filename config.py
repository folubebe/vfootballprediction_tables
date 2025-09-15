"""
Configuration file for Virtual Football Prediction System - COMPLETE VERSION
"""

# League name standardization mapping
LEAGUE_NAME_MAPPING = {
    # Raw names from Selenium -> Standardized names
    'england': 'england virtual',
    'spain': 'spain virtual', 
    'italy': 'italy virtual',
    'germany': 'germany virtual',
    'france': 'france virtual',
    
    # Handle variations you might encounter
    'england virtual': 'england virtual',
    'spain virtual': 'spain virtual',
    'italy virtual': 'italy virtual', 
    'germany virtual': 'germany virtual',
    'france virtual': 'france virtual',
    
    # Handle title case variations
    'England': 'england virtual',
    'Spain': 'spain virtual',
    'Italy': 'italy virtual',
    'Germany': 'germany virtual', 
    'France': 'france virtual',
    
    'England Virtual': 'england virtual',
    'Spain Virtual': 'spain virtual',
    'Italy Virtual': 'italy virtual',
    'Germany Virtual': 'germany virtual',
    'France Virtual': 'france virtual',
}

# Virtual league IDs (from your API)
VIRTUAL_LEAGUES = {
    'england virtual': 'sv:category:202120001',
    'spain virtual': 'sv:category:202120002', 
    'italy virtual': 'sv:category:202120003',
    'germany virtual': 'sv:category:202120004',
    'france virtual': 'sv:category:202120005'
}

# Display names for frontend
DISPLAY_NAMES = {
    'england virtual': 'England Virtual League',
    'spain virtual': 'Spain Virtual League',
    'italy virtual': 'Italy Virtual League', 
    'germany virtual': 'Germany Virtual League',
    'france virtual': 'France Virtual League'
}

def standardize_league_name(league_name):
    """
    Standardize league names to consistent format.
    
    Args:
        league_name (str): Raw league name from any source
        
    Returns:
        str: Standardized league name
    """
    if not league_name:
        return 'unknown virtual'
    
    # Clean the input
    league_name = str(league_name).strip()
    
    # Try exact match first
    if league_name.lower() in LEAGUE_NAME_MAPPING:
        return LEAGUE_NAME_MAPPING[league_name.lower()]
    
    # Try with original case
    if league_name in LEAGUE_NAME_MAPPING:
        return LEAGUE_NAME_MAPPING[league_name]
    
    # If contains any known league name, extract it
    league_lower = league_name.lower()
    for raw_name, standard_name in LEAGUE_NAME_MAPPING.items():
        if raw_name.lower() in league_lower:
            return standard_name
    
    # Default: make it virtual
    league_base = league_name.lower().replace('virtual', '').strip()
    return f"{league_base} virtual"

def get_display_name(league_name):
    """
    Get display-friendly league name.
    
    Args:
        league_name (str): Standardized league name
        
    Returns:
        str: Display name
    """
    if not league_name:
        return "Unknown Virtual League"
    
    standardized = standardize_league_name(league_name)
    return DISPLAY_NAMES.get(standardized, standardized.title())

def debug_league_mapping(input_name):
    """
    Debug function to see how a league name gets processed.
    """
    print(f"Input: '{input_name}'")
    print(f"Standardized: '{standardize_league_name(input_name)}'")
    print(f"Display: '{get_display_name(input_name)}'")

# Test the mapping
if __name__ == '__main__':
    test_names = [
        'england', 'England', 'ENGLAND', 
        'spain virtual', 'Spain Virtual',
        'italy', 'Germany', 'france',
        'England Virtual League',
        'unknown league'
    ]
    
    print("Testing league name standardization:")
    print("=" * 50)
    for name in test_names:
        debug_league_mapping(name)
        print("-" * 30)
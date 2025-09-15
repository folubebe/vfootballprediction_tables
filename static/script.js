document.addEventListener('DOMContentLoaded', () => {
    const leagueSelect = document.getElementById('league-select');
    const matchesDiv = document.getElementById('matches');
    const predictionDiv = document.getElementById('prediction');
    const leagueTableDiv = document.getElementById('league-table');
    const tableBody = document.getElementById('table-body');
    const baseUrl = 'http://127.0.0.1:5000';

    let tableData = [];

    // Fetch leagues with improved error handling and deduplication
    fetch(`${baseUrl}/leagues`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Leagues data:', data); // Debug log
            
            if (data.leagues && Array.isArray(data.leagues)) {
                // Handle new league structure with display names
                data.leagues.forEach(league => {
                    const option = document.createElement('option');
                    option.value = typeof league === 'string' ? league : league.value;
                    option.textContent = typeof league === 'string' ? 
                        league.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ') :
                        league.display;
                    leagueSelect.appendChild(option);
                });
                
                console.log(`Loaded ${data.leagues.length} unique leagues`);
            } else {
                console.error('Invalid leagues data structure:', data);
                showError('Invalid league data received from server');
            }
        })
        .catch(error => {
            console.error('Error fetching leagues:', error);
            showError('Failed to load leagues. Please check if the server is running.');
        });

    // Fetch matches and league table when league is selected
    leagueSelect.addEventListener('change', () => {
        const league = leagueSelect.value;
        clearContent();

        if (league) {
            console.log(`Selected league: ${league}`); // Debug log
            
            // Show loading indicators
            matchesDiv.innerHTML = '<div class="bg-white p-4 rounded-lg shadow"><p class="text-gray-500">Loading matches...</p></div>';
            tableBody.innerHTML = '<tr><td colspan="11" class="text-center text-gray-500">Loading table...</td></tr>';
            leagueTableDiv.classList.remove('hidden');

            // Fetch matches (scheduled and historical)
            fetchMatches(league);
            
            // Fetch league table
            fetchLeagueTable(league);
        }
    });

    function fetchMatches(league) {
        fetch(`${baseUrl}/matches/${encodeURIComponent(league)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`Matches data for ${league}:`, data); // Debug log
                
                matchesDiv.innerHTML = ''; // Clear loading message
                
                if (data.matches && data.matches.length > 0) {
                    // Update page title with league display name
                    if (data.league_display) {
                        document.querySelector('h1').textContent = `${data.league_display} - Virtual Football Predictions`;
                    }
                    
                    data.matches.forEach(match => {
                        const matchDiv = createMatchCard(match, league);
                        matchesDiv.appendChild(matchDiv);
                    });
                    
                    console.log(`Loaded ${data.matches.length} matches`);
                } else {
                    showNoMatches(`No matches available for ${league}`);
                }
            })
            .catch(error => {
                console.error('Error fetching matches:', error);
                showError('Failed to load matches for this league');
            });
    }

    function fetchLeagueTable(league) {
        fetch(`${baseUrl}/league_table/${encodeURIComponent(league)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`Table data for ${league}:`, data); // Debug log
                
                tableBody.innerHTML = ''; // Clear loading message
                
                if (data.league_table && data.league_table.length > 0) {
                    tableData = data.league_table.map(team => ({
                        ...team,
                        goal_difference: team.goals_for - team.goals_against
                    }));
                    renderTable(tableData);
                    
                    // Update table header with league display name
                    if (data.league_display) {
                        document.querySelector('#league-table h2').textContent = `${data.league_display} - League Table`;
                    }
                    
                    console.log(`Loaded table with ${tableData.length} teams`);
                } else {
                    tableBody.innerHTML = '<tr><td colspan="11" class="text-center text-gray-500">No table data available for this league</td></tr>';
                }
            })
            .catch(error => {
                console.error('Error fetching league table:', error);
                tableBody.innerHTML = '<tr><td colspan="11" class="text-center text-red-500">Error loading table</td></tr>';
            });
    }

    function createMatchCard(match, league) {
        const matchDiv = document.createElement('div');
        matchDiv.className = 'bg-white p-4 rounded-lg shadow match-card cursor-pointer';
        matchDiv.dataset.homeTeam = match.home_team;
        matchDiv.dataset.awayTeam = match.away_team;
        matchDiv.dataset.league = league;
        matchDiv.dataset.eventId = match.event_id;
        
        // Different styling based on match type and prediction availability
        const statusColor = match.type === 'scheduled' ? 'text-green-600' : 'text-blue-600';
        const statusText = match.type === 'scheduled' ? 'Upcoming' : 'Historical';
        const predictionIcon = match.can_predict ? '🎯' : '❌';
        const predictionClass = match.can_predict ? 'text-green-600' : 'text-orange-500';
        const cardClass = match.can_predict ? 'hover:bg-green-50' : 'hover:bg-orange-50';
        
        matchDiv.className += ` ${cardClass}`;
        
        matchDiv.innerHTML = `
            <h3 class="text-lg font-semibold">${match.home_team} vs ${match.away_team}</h3>
            <p class="text-sm text-gray-600">${match.match_time}</p>
            <p class="text-xs ${statusColor}">${statusText}</p>
            <p class="text-xs ${predictionClass}">${predictionIcon} ${match.prediction_note}</p>
        `;
        
        // Only add click handler if prediction is available
        if (match.can_predict) {
            matchDiv.addEventListener('click', () => {
                fetchPrediction(league, match.home_team, match.away_team);
            });
        } else {
            matchDiv.style.cursor = 'not-allowed';
            matchDiv.style.opacity = '0.7';
        }
        
        return matchDiv;
    }

    // Fetch prediction for selected match
    function fetchPrediction(league, homeTeam, awayTeam) {
        console.log(`Fetching prediction for: ${homeTeam} vs ${awayTeam} in ${league}`); // Debug log
        
        // Show loading message
        predictionDiv.innerHTML = '<p class="text-gray-500">Loading prediction...</p>';
        predictionDiv.classList.remove('hidden');
        
        fetch(`${baseUrl}/predict/${encodeURIComponent(league)}/${encodeURIComponent(homeTeam)}/${encodeURIComponent(awayTeam)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Prediction data:', data); // Debug log
                
                if (data.prediction) {
                    const pred = data.prediction;
                    predictionDiv.innerHTML = `
                        <h2 class="text-xl font-bold mb-2">Prediction: ${homeTeam} vs ${awayTeam}</h2>
                        <div class="mb-4 p-4 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg border">
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                <div class="text-center p-3 bg-white rounded shadow">
                                    <p class="text-sm text-gray-600">Home Win</p>
                                    <p class="text-2xl font-bold text-blue-600">${pred.home_win_prob}%</p>
                                </div>
                                <div class="text-center p-3 bg-white rounded shadow">
                                    <p class="text-sm text-gray-600">Draw</p>
                                    <p class="text-2xl font-bold text-gray-600">${pred.draw_prob}%</p>
                                </div>
                                <div class="text-center p-3 bg-white rounded shadow">
                                    <p class="text-sm text-gray-600">Away Win</p>
                                    <p class="text-2xl font-bold text-red-600">${pred.away_win_prob}%</p>
                                </div>
                            </div>
                            <div class="text-center mb-4">
                                <p class="text-lg"><strong>Predicted Result:</strong> ${pred.predicted_result} (${pred.predicted_score})</p>
                                <p class="text-md mt-2">
                                    <span class="inline-block bg-blue-100 text-blue-800 px-3 py-1 rounded-full mr-2">
                                        Over 2.5 Goals: ${pred.over_2_5}
                                    </span>
                                    <span class="inline-block bg-green-100 text-green-800 px-3 py-1 rounded-full">
                                        Both Teams Score: ${pred.btts}
                                    </span>
                                </p>
                            </div>
                        </div>
                        <div class="bg-gray-50 p-4 rounded-lg">
                            <h3 class="font-semibold mb-2">Detailed Analysis:</h3>
                            <div class="text-sm whitespace-pre-wrap">${pred.formatted}</div>
                        </div>
                    `;
                } else {
                    predictionDiv.innerHTML = '<p class="text-red-500">Prediction unavailable - insufficient historical data for these teams</p>';
                }
            })
            .catch(error => {
                console.error('Error fetching prediction:', error);
                predictionDiv.innerHTML = '<p class="text-red-500">Error fetching prediction. Please try again.</p>';
            });
    }

    // Render table with data
    function renderTable(data) {
        tableBody.innerHTML = '';
        data.forEach(team => {
            const row = document.createElement('tr');
            
            // Add position-based styling
            let positionClass = '';
            if (team.position <= 3) positionClass = 'bg-green-50';
            else if (team.position >= data.length - 2) positionClass = 'bg-red-50';
            
            row.className = positionClass;
            row.innerHTML = `
                <td class="font-semibold">${team.position}</td>
                <td class="text-left font-medium">${team.team_name}</td>
                <td class="font-bold text-lg">${team.points}</td>
                <td>${team.matches_played}</td>
                <td class="text-green-600">${team.wins}</td>
                <td class="text-gray-600">${team.draws}</td>
                <td class="text-red-600">${team.losses}</td>
                <td class="text-blue-600">${team.goals_for}</td>
                <td class="text-red-500">${team.goals_against}</td>
                <td class="font-medium ${team.goal_difference >= 0 ? 'text-green-600' : 'text-red-600'}">
                    ${team.goal_difference >= 0 ? '+' : ''}${team.goal_difference}
                </td>
                <td class="text-xs font-mono">${formatLastResults(team.last_5_results)}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    // Format last 5 results with colors
    function formatLastResults(results) {
        if (!results) return '';
        return results.split('').map(result => {
            const color = result === 'W' ? 'text-green-600' : 
                         result === 'D' ? 'text-yellow-600' : 'text-red-600';
            return `<span class="${color}">${result}</span>`;
        }).join(' ');
    }

    // Utility functions
    function clearContent() {
        matchesDiv.innerHTML = '';
        tableBody.innerHTML = '';
        predictionDiv.classList.add('hidden');
        leagueTableDiv.classList.add('hidden');
        document.querySelector('h1').textContent = 'Virtual Football Predictions'; // Reset title
    }

    function showError(message) {
        matchesDiv.innerHTML = `<div class="bg-red-50 border border-red-200 p-4 rounded-lg shadow">
            <p class="text-red-600">⚠️ ${message}</p>
        </div>`;
    }

    function showNoMatches(message) {
        matchesDiv.innerHTML = `<div class="bg-yellow-50 border border-yellow-200 p-4 rounded-lg shadow">
            <p class="text-yellow-700">ℹ️ ${message}</p>
        </div>`;
    }

    // Table sorting functionality
    document.querySelectorAll('th[data-sort]').forEach(header => {
        header.addEventListener('click', () => {
            const sortKey = header.dataset.sort;
            const isNumeric = ['position', 'points', 'matches_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'goal_difference'].includes(sortKey);
            const ascending = header.classList.contains('sort-asc');

            // Remove sorting classes from all headers
            document.querySelectorAll('th[data-sort]').forEach(h => {
                h.classList.remove('sort-asc', 'sort-desc');
            });

            tableData.sort((a, b) => {
                const aValue = isNumeric ? Number(a[sortKey]) : (a[sortKey] || '').toLowerCase();
                const bValue = isNumeric ? Number(b[sortKey]) : (b[sortKey] || '').toLowerCase();
                return ascending
                    ? (aValue > bValue ? -1 : aValue < bValue ? 1 : 0)
                    : (aValue < bValue ? -1 : aValue > bValue ? 1 : 0);
            });

            header.classList.toggle('sort-asc', !ascending);
            header.classList.toggle('sort-desc', ascending);
            renderTable(tableData);
        });
    });

    // Debug function - improved with better error handling
    const debugButton = document.createElement('button');
    debugButton.textContent = 'Debug Database';
    debugButton.className = 'fixed bottom-4 right-4 bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded shadow-lg transition-colors';
    debugButton.addEventListener('click', () => {
        fetch(`${baseUrl}/debug/database`)
            .then(response => response.json())
            .then(data => {
                console.log('Database Debug Info:', data);
                
                const status = data.database_status;
                const leagues = status.standardized_leagues || [];
                
                let debugMessage = `Database Status:
Scheduled: ${status.scheduled_matches_count}
Completed: ${status.completed_matches_count}
Tables: ${status.league_tables_count}

Leagues found:
${leagues.map(l => `• ${l.raw} → ${l.standardized} (${l.display})`).join('\n')}`;
                
                alert(debugMessage);
            })
            .catch(error => {
                console.error('Debug error:', error);
                alert('Debug request failed. Check console for details.');
            });
    });
    document.body.appendChild(debugButton);
});
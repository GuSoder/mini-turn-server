from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
from enum import Enum
import logging
import json

class Phase(Enum):
    PLANNING = "planning"
    MOVING = "moving"

# Configuration - set to 4 to maintain current functionality
MAX_ENTITIES = 4

app = Flask(__name__)
CORS(app)

# Configure logging to suppress GET requests
class NoGetFilter(logging.Filter):
    def filter(self, record):
        return 'GET' not in record.getMessage()

# Apply filter to werkzeug logger (handles HTTP requests)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(NoGetFilter())

games = {}

def is_adjacent_hex(pos1, pos2):
    """Check if two hex coordinates are adjacent using simple distance"""
    q1, r1 = pos1['q'], pos1['r']
    q2, r2 = pos2['q'], pos2['r']
    
    # Calculate simple distance between grid positions
    diff_q, diff_r = abs(q2 - q1), abs(r2 - r1)
    
    # Adjacent if exactly 1 step in any direction (including diagonals)
    return (diff_q <= 1 and diff_r <= 1) and (diff_q + diff_r > 0)

def validate_path(path):
    """Validate that path is a sequence of adjacent hexes"""
    if len(path) < 1:
        return False
    
    for i in range(1, len(path)):
        if not is_adjacent_hex(path[i-1], path[i]):
            return False
    
    return True

def get_next_alive_player(game, current_player):
    """Find the next entity that's still alive (health > 0)"""
    for i in range(MAX_ENTITIES):  # Try up to MAX_ENTITIES times to find next alive entity
        next_player = (current_player + 1 + i) % MAX_ENTITIES
        if game['stats'][next_player]['health'] > 0:
            return next_player
    return -1  # No alive entities found

@app.route('/games', methods=['GET'])
def list_games():
    """List all active games"""
    game_list = []
    for game_id, game_data in games.items():
        game_list.append({
            "gameId": game_id,
            "playerInTurn": game_data["playerInTurn"],
            "phase": game_data["phase"],
            "playerCount": MAX_ENTITIES
        })
    return jsonify({"games": game_list})

@app.route('/games', methods=['POST'])
def create_game():
    """Create a new game"""
    game_id = str(uuid.uuid4())

    # Define all 8 possible starting positions (first 4 are original player positions)
    all_positions = [
        {"q": 4, "r": 3},  # Player 1 (original)
        {"q": 6, "r": 3},  # Player 2 (original)
        {"q": 3, "r": 5},  # Player 3 (original)
        {"q": 7, "r": 4},  # Player 4 (original)
        {"q": 2, "r": 2},  # Enemy 1 (new)
        {"q": 8, "r": 2},  # Enemy 2 (new)
        {"q": 1, "r": 7},  # Enemy 3 (new)
        {"q": 9, "r": 6}   # Enemy 4 (new)
    ]

    # Use only the first MAX_ENTITIES positions
    active_positions = all_positions[:MAX_ENTITIES]
    active_paths = [[pos] for pos in active_positions]
    active_stats = [{"health": 10, "max_health": 10, "strength": 5} for _ in range(MAX_ENTITIES)]

    games[game_id] = {
        "positions": active_positions,
        "playerInTurn": 0,
        "phase": Phase.PLANNING.value,
        "lastPaths": active_paths,
        "stats": active_stats,
        "map": "overworld"
    }
    return jsonify({"gameId": game_id})

@app.route('/games/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    """Get current game state"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    return jsonify(games[game_id])

@app.route('/games/<game_id>/move', methods=['POST'])
def make_move(game_id):
    """Make a move in the game"""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    game = games[game_id]
    data = request.get_json()
    
    if not data or 'player' not in data or 'path' not in data:
        return jsonify({"ok": False, "error": "Invalid request"})
    
    player = data['player']
    path = data['path']
    
    # Validate entity number
    if player < 0 or player >= MAX_ENTITIES:
        return jsonify({"ok": False, "error": "Invalid player"})
    
    # Check if it's the player's turn
    if game['playerInTurn'] != player:
        return jsonify({"ok": False, "error": "Not your turn"})
    
    # Check if we're in planning phase
    if game['phase'] != Phase.PLANNING.value:
        return jsonify({"ok": False, "error": "Not in planning phase"})
    
    # Validate path
    if not path or len(path) == 0:
        return jsonify({"ok": False, "error": "Empty path"})
    
    # Check first position matches current position
    current_pos = game['positions'][player]
    if path[0]['q'] != current_pos['q'] or path[0]['r'] != current_pos['r']:
        return jsonify({"ok": False, "error": "Path must start from current position"})
    
    # Validate each step is adjacent
    if not validate_path(path):
        return jsonify({"ok": False, "error": "Invalid path - non-adjacent hexes"})
    
    # Apply the move
    game['positions'][player] = path[-1]
    game['lastPaths'][player] = path
    game['phase'] = Phase.MOVING.value
    print(f"PHASE: Player {player} move accepted, changed to MOVING phase")
    
    return jsonify({"ok": True})

@app.route('/games/<game_id>/attack', methods=['POST'])
def attack(game_id):
    """Handle an attack between players"""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    game = games[game_id]
    data = request.get_json()
    
    if not data or 'attacker' not in data or 'target' not in data:
        return jsonify({"ok": False, "error": "Invalid request"})
    
    attacker = data['attacker']
    target = data['target']
    
    # Validate entity numbers
    if attacker < 0 or attacker >= MAX_ENTITIES or target < 0 or target >= MAX_ENTITIES:
        return jsonify({"ok": False, "error": "Invalid player numbers"})
    
    # Check if it's the attacker's turn
    if game['playerInTurn'] != attacker:
        return jsonify({"ok": False, "error": "Not your turn"})
    
    # Check if we're in moving phase
    if game['phase'] != Phase.MOVING.value:
        return jsonify({"ok": False, "error": "Not in moving phase"})
    
    # Can't attack yourself
    if attacker == target:
        return jsonify({"ok": False, "error": "Cannot attack yourself"})
    
    # Check if target is adjacent to attacker's current position
    attacker_pos = game['positions'][attacker]
    target_pos = game['positions'][target]
    
    if not is_adjacent_hex(attacker_pos, target_pos):
        return jsonify({"ok": False, "error": "Target not adjacent"})
    
    # Check if target is still alive
    if game['stats'][target]['health'] <= 0:
        return jsonify({"ok": False, "error": "Target is already dead"})
    
    # Apply damage
    attacker_strength = game['stats'][attacker]['strength']
    game['stats'][target]['health'] -= attacker_strength
    
    # Ensure health doesn't go below 0
    if game['stats'][target]['health'] < 0:
        game['stats'][target]['health'] = 0
    
    print(f"ATTACK!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!: Player {attacker} attacked Player {target} for {attacker_strength} damage. Target health: {game['stats'][target]['health']}")
    
    return jsonify({"ok": True})

@app.route('/games/<game_id>/end_turn', methods=['POST'])
def end_turn(game_id):
    """End the current player's turn"""
    print(f"END_TURN: Received end_turn request for game {game_id}")
    
    if game_id not in games:
        print(f"END_TURN: Game {game_id} not found")
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    game = games[game_id]
    data = request.get_json()
    
    print(f"END_TURN: Request data: {data}")
    print(f"END_TURN: Current state - playerInTurn: {game['playerInTurn']}, phase: {game['phase']}")
    
    if not data or 'player' not in data:
        print("END_TURN: Invalid request - missing player")
        return jsonify({"ok": False, "error": "Invalid request"})
    
    player = data['player']
    
    # Validate entity number
    if player < 0 or player >= MAX_ENTITIES:
        print(f"END_TURN: Invalid player number: {player}")
        return jsonify({"ok": False, "error": "Invalid player"})
    
    # Check if it's the player's turn
    if game['playerInTurn'] != player:
        print(f"END_TURN: Not player's turn - expected {game['playerInTurn']}, got {player}")
        return jsonify({"ok": False, "error": "Not your turn"})
    
    # Check if we're in moving phase
    if game['phase'] != Phase.MOVING.value:
        print(f"END_TURN: Not in moving phase - current phase: {game['phase']}")
        return jsonify({"ok": False, "error": "Not in moving phase"})
    
    # Increment turn and reset to planning phase, skipping dead players
    old_player = game['playerInTurn']
    next_player = get_next_alive_player(game, old_player)
    
    if next_player == -1:
        print(f"GAME_END: No alive players found after player {old_player} ended turn")
        # Could add game end logic here
        return jsonify({"ok": False, "error": "Game over - no alive players"})
    
    game['playerInTurn'] = next_player
    game['phase'] = Phase.PLANNING.value
    print(f"PHASE: Player {old_player} ended turn, now Player {game['playerInTurn']} turn in PLANNING phase")
    
    return jsonify({"ok": True})

@app.route('/games/<game_id>/set_map', methods=['POST'])
def set_map(game_id):
    """Set the current map for a game"""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404

    data = request.get_json()
    if not data or 'map' not in data:
        return jsonify({"ok": False, "error": "Invalid request - map field required"})

    map_name = data['map']
    games[game_id]['map'] = map_name
    print(f"MAP: Game {game_id} map changed to {map_name}")

    return jsonify({"ok": True})

@app.route('/map/<map_name>', methods=['GET'])
def get_map(map_name):
    """Get map data by name"""
    try:
        with open(f'maps/{map_name}.txt', 'r') as f:
            lines = [line.strip() for line in f.readlines()]
        return jsonify({"map": lines})
    except FileNotFoundError:
        return jsonify({"error": f"Map {map_name} not found"}), 404

@app.route('/island/<int:island_num>', methods=['GET'])
def get_island(island_num):
    """Get island map data by number"""
    try:
        with open(f'islands/island{island_num}.txt', 'r') as f:
            lines = [line.strip() for line in f.readlines()]
        return jsonify({"map": lines})
    except FileNotFoundError:
        return jsonify({"error": f"Island {island_num} map not found"}), 404

@app.route('/scenario/<scenario_name>', methods=['GET'])
def get_scenario(scenario_name):
    """Get scenario data by name"""
    try:
        with open(f'scenarios/{scenario_name}.json', 'r') as f:
            scenario_data = json.load(f)
        return jsonify(scenario_data)
    except FileNotFoundError:
        return jsonify({"error": f"Scenario {scenario_name} not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": f"Invalid JSON in scenario {scenario_name}"}), 500

@app.route('/scenarios', methods=['GET'])
def list_scenarios():
    """List all available scenarios"""
    try:
        import os
        scenario_files = [f[:-5] for f in os.listdir('scenarios') if f.endswith('.json')]
        scenarios = []
        for scenario_name in scenario_files:
            try:
                with open(f'scenarios/{scenario_name}.json', 'r') as f:
                    scenario_data = json.load(f)
                scenarios.append({
                    "name": scenario_name,
                    "title": scenario_data.get("name", scenario_name),
                    "description": scenario_data.get("description", ""),
                    "map": scenario_data.get("map", "")
                })
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        return jsonify({"scenarios": scenarios})
    except FileNotFoundError:
        return jsonify({"scenarios": []})

@app.route('/games/<game_id>/set_scenario', methods=['POST'])
def set_scenario(game_id):
    """Set the scenario for a game, loading positions and map from scenario file"""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404

    data = request.get_json()
    if not data or 'scenario' not in data:
        return jsonify({"ok": False, "error": "Invalid request - scenario field required"})

    scenario_name = data['scenario']

    try:
        with open(f'scenarios/{scenario_name}.json', 'r') as f:
            scenario_data = json.load(f)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Scenario {scenario_name} not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"ok": False, "error": f"Invalid JSON in scenario {scenario_name}"}), 500

    # Update game state with scenario data
    game = games[game_id]

    # Set map from scenario
    if "map" in scenario_data:
        game['map'] = scenario_data['map']
        print(f"SCENARIO: Game {game_id} map set to {scenario_data['map']}")

    # Set entity positions from scenario
    if "player_positions" in scenario_data:
        positions = scenario_data['player_positions']
        if len(positions) >= MAX_ENTITIES:
            for i in range(MAX_ENTITIES):
                if i < len(positions):
                    game['positions'][i] = positions[i]
                    # Also update lastPaths to reflect new positions
                    game['lastPaths'][i] = [positions[i]]
            print(f"SCENARIO: Game {game_id} positions updated from scenario {scenario_name}")

    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

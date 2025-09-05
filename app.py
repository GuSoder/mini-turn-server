from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
from enum import Enum

class Phase(Enum):
    PLANNING = "planning"
    MOVING = "moving"

app = Flask(__name__)
CORS(app)

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
    """Find the next player that's still alive (health > 0)"""
    for i in range(4):  # Try up to 4 times to find next alive player
        next_player = (current_player + 1 + i) % 4
        if game['stats'][next_player]['health'] > 0:
            return next_player
    return -1  # No alive players found

@app.route('/games', methods=['GET'])
def list_games():
    """List all active games"""
    game_list = []
    for game_id, game_data in games.items():
        game_list.append({
            "gameId": game_id,
            "playerInTurn": game_data["playerInTurn"],
            "phase": game_data["phase"],
            "playerCount": 4
        })
    return jsonify({"games": game_list})

@app.route('/games', methods=['POST'])
def create_game():
    """Create a new game"""
    game_id = str(uuid.uuid4())
    games[game_id] = {
        "positions": [
            {"q": 4, "r": 4},
            {"q": 6, "r": 3}, 
            {"q": 3, "r": 5},
            {"q": 7, "r": 4}
        ],
        "playerInTurn": 0,
        "phase": Phase.PLANNING.value,
        "lastPaths": [
            [{"q": 4, "r": 4}],
            [{"q": 6, "r": 3}],
            [{"q": 3, "r": 5}], 
            [{"q": 7, "r": 4}]
        ],
        "stats": [
            {"health": 10, "max_health": 10, "strength": 5},
            {"health": 10, "max_health": 10, "strength": 5},
            {"health": 10, "max_health": 10, "strength": 5},
            {"health": 10, "max_health": 10, "strength": 5}
        ]
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
    
    # Validate player number
    if player < 0 or player > 3:
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
    
    # Validate player numbers
    if attacker < 0 or attacker > 3 or target < 0 or target > 3:
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
    
    print(f"ATTACK: Player {attacker} attacked Player {target} for {attacker_strength} damage. Target health: {game['stats'][target]['health']}")
    
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
    
    # Validate player number
    if player < 0 or player > 3:
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
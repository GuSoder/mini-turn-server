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

@app.route('/games/<game_id>/end_turn', methods=['POST'])
def end_turn(game_id):
    """End the current player's turn"""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    game = games[game_id]
    data = request.get_json()
    
    if not data or 'player' not in data:
        return jsonify({"ok": False, "error": "Invalid request"})
    
    player = data['player']
    
    # Validate player number
    if player < 0 or player > 3:
        return jsonify({"ok": False, "error": "Invalid player"})
    
    # Check if it's the player's turn
    if game['playerInTurn'] != player:
        return jsonify({"ok": False, "error": "Not your turn"})
    
    # Check if we're in moving phase
    if game['phase'] != Phase.MOVING.value:
        return jsonify({"ok": False, "error": "Not in moving phase"})
    
    # Increment turn and reset to planning phase
    old_player = game['playerInTurn']
    game['playerInTurn'] = (game['playerInTurn'] + 1) % 4
    game['phase'] = Phase.PLANNING.value
    print(f"PHASE: Player {old_player} ended turn, now Player {game['playerInTurn']} turn in PLANNING phase")
    
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
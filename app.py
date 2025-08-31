from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

games = {}

def is_adjacent_hex(pos1, pos2):
    """Check if two hex coordinates are adjacent"""
    q1, r1 = pos1['q'], pos1['r']
    q2, r2 = pos2['q'], pos2['r']
    
    # Hex neighbors: (0,1), (1,0), (1,-1), (0,-1), (-1,0), (-1,1)
    neighbors = [(0,1), (1,0), (1,-1), (0,-1), (-1,0), (-1,1)]
    diff_q, diff_r = q2 - q1, r2 - r1
    
    return (diff_q, diff_r) in neighbors

def validate_path(path):
    """Validate that path is a sequence of adjacent hexes"""
    if len(path) < 1:
        return False
    
    for i in range(1, len(path)):
        if not is_adjacent_hex(path[i-1], path[i]):
            return False
    
    return True

@app.route('/games', methods=['POST'])
def create_game():
    """Create a new game"""
    game_id = str(uuid.uuid4())
    games[game_id] = {
        "positions": [
            {"q": 0, "r": 0},
            {"q": 2, "r": -1}, 
            {"q": -1, "r": 1},
            {"q": 3, "r": 0}
        ],
        "playerInTurn": 0,
        "lastPaths": [
            [{"q": 0, "r": 0}],
            [{"q": 2, "r": -1}],
            [{"q": -1, "r": 1}], 
            [{"q": 3, "r": 0}]
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
    game['playerInTurn'] = (game['playerInTurn'] + 1) % 4
    
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
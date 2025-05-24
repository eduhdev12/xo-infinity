import uuid
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class PlayerSymbol(str, Enum):
    X = "X"
    O = "O"

@dataclass
class Player:
    name: str
    symbol: PlayerSymbol
    websocket: Optional[object] = None

@dataclass
class GameRoom:
    id: str
    players: Dict[str, Player]
    board: Dict[Tuple[int, int], str]
    current_turn: str
    is_game_over: bool = False
    winner: Optional[str] = None

def check_win_condition(room: GameRoom, last_x: int, last_y: int) -> Dict:
    """Check if the last move resulted in a win"""
    symbol = room.board[(last_x, last_y)]
    
    # Check all possible directions for a win
    directions = [
        [(0, 1), (0, -1)],  # Vertical
        [(1, 0), (-1, 0)],  # Horizontal
        [(1, 1), (-1, -1)], # Diagonal
        [(1, -1), (-1, 1)]  # Anti-diagonal
    ]
    
    for dir_pair in directions:
        count = 1  # Count the last move
        
        # Check in both directions
        for dx, dy in dir_pair:
            x, y = last_x, last_y
            while True:
                x += dx
                y += dy
                if (x, y) not in room.board or room.board[(x, y)] != symbol:
                    break
                count += 1
                
        if count >= 5:  # Win condition: 5 in a row
            return {"is_win": True, "direction": dir_pair}
            
    return {"is_win": False}

def make_move(room: GameRoom, player: Player, x: int, y: int) -> Dict:
    """Make a move in the game"""
    if room.is_game_over:
        return {"success": False, "message": "Game is over"}
        
    if player.name != room.current_turn:
        return {"success": False, "message": "Not your turn"}
        
    if (x, y) in room.board:
        return {"success": False, "message": "Position already taken"}
        
    # Make the move
    room.board[(x, y)] = player.symbol
    
    # Switch turns
    other_player = next(p for p in room.players.values() if p.name != player.name)
    room.current_turn = other_player.name
    
    return {"success": True}

def create_room(rooms: Dict[str, GameRoom], player_name: str) -> Tuple[str, Player]:
    """Create a new game room"""
    room_id = str(uuid.uuid4())[:8]
    player = Player(name=player_name, symbol=PlayerSymbol.X)
    room = GameRoom(
        id=room_id,
        players={player_name: player},
        board={},
        current_turn=player_name
    )
    rooms[room_id] = room
    return room_id, player

def join_room(room: GameRoom, player_name: str, symbol: str) -> Player:
    """Join an existing game room"""
    if len(room.players) >= 2:
        raise ValueError("Room is full")
        
    if player_name in room.players:
        raise ValueError("Player name already taken")
        
    # Validate symbol
    if symbol not in [PlayerSymbol.X, PlayerSymbol.O]:
        raise ValueError("Invalid symbol")
        
    # Check if symbol is already taken
    for player in room.players.values():
        if player.symbol == symbol:
            raise ValueError("Symbol already taken")
            
    player = Player(name=player_name, symbol=PlayerSymbol(symbol))
    room.players[player_name] = player
    return player 
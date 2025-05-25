import uuid
from typing import Dict, Optional, Tuple, List, Set
from dataclasses import dataclass
from enum import Enum
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameError(Exception):
    """Base exception for game-related errors"""
    pass

class InvalidMoveError(GameError):
    """Raised when an invalid move is attempted"""
    pass

class GameStateError(GameError):
    """Raised when there's an invalid game state"""
    pass

class PlayerSymbol(str, Enum):
    X = "X"
    O = "O"

@dataclass
class Player:
    name: str
    symbol: PlayerSymbol
    client_id: Optional[str] = None

@dataclass
class GameRoom:
    id: str
    players: Dict[str, Player]
    board: Dict[Tuple[int, int], PlayerSymbol]
    current_turn: str
    is_game_over: bool = False
    winner: Optional[str] = None
    last_move: Optional[Tuple[int, int]] = None
    created_at: float = 0.0  # Timestamp for room creation

    def validate_state(self) -> bool:
        """Validate the current game state"""
        if len(self.players) > 2:
            return False
        if self.is_game_over and not self.winner:
            return False
        return True

def get_winning_positions(room: GameRoom, last_x: int, last_y: int) -> Optional[List[Tuple[int, int]]]:
    """Get the winning positions if there's a win"""
    if (last_x, last_y) not in room.board:
        return None
        
    symbol = room.board[(last_x, last_y)]
    
    # Check all possible directions for a win
    directions = [
        [(0, 1), (0, -1)],  # Vertical
        [(1, 0), (-1, 0)],  # Horizontal
        [(1, 1), (-1, -1)], # Diagonal
        [(1, -1), (-1, 1)]  # Anti-diagonal
    ]
    
    for dir_pair in directions:
        positions = [(last_x, last_y)]
        
        # Check in both directions
        for dx, dy in dir_pair:
            x, y = last_x, last_y
            count = 1
            while True:
                x += dx
                y += dy
                if (x, y) not in room.board or room.board[(x, y)] != symbol:
                    break
                positions.append((x, y))
                count += 1
                
        if len(positions) >= 5:  # Win condition: 5 in a row
            return positions
            
    return None

def check_draw_condition(room: GameRoom) -> bool:
    """Check if the game is a draw by checking if there are any empty spaces"""
    # Get the bounds of the current board
    if not room.board:
        return False
        
    x_coords = [x for x, _ in room.board.keys()]
    y_coords = [y for _, y in room.board.keys()]
    
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    
    # Check if there are any empty spaces within the bounds
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            if (x, y) not in room.board:
                return False
                
    return True

def check_win_condition(room: GameRoom, last_x: int, last_y: int) -> Dict:
    """Check if the last move resulted in a win"""
    winning_positions = get_winning_positions(room, last_x, last_y)
    
    return {
        "is_win": winning_positions is not None,
        "winning_positions": winning_positions,
        "is_draw": False  # Draw is not possible in infinite board
    }

def make_move(room: GameRoom, player: Player, x: int, y: int) -> Dict:
    """Make a move in the game"""
    if not room.validate_state():
        raise GameStateError("Invalid game state")
        
    if room.is_game_over:
        raise InvalidMoveError("Game is over")
        
    if player.name != room.current_turn:
        raise InvalidMoveError("Not your turn")
        
    if (x, y) in room.board:
        raise InvalidMoveError("Position already taken")
        
    # Make the move
    room.board[(x, y)] = player.symbol
    room.last_move = (x, y)
    
    # Check win condition
    win_result = check_win_condition(room, x, y)
    
    if win_result["is_win"]:
        room.is_game_over = True
        room.winner = player.name
        return {
            "success": True,
            "is_win": True,
            "winning_positions": win_result["winning_positions"],
            "winner": player.name,
            "is_game_over": True
        }
    
    # Switch turns
    other_player = next(p for p in room.players.values() if p.name != player.name)
    room.current_turn = other_player.name
    
    return {
        "success": True,
        "is_win": False,
        "is_draw": False,
        "winner": None,
        "is_game_over": False
    }

def create_room(rooms: Dict[str, GameRoom], player_name: str, client_id: str) -> Tuple[str, Player]:
    """Create a new game room"""
    if not player_name or len(player_name) > 20:
        raise ValueError("Invalid player name")
        
    room_id = str(uuid.uuid4())[:8]
    player = Player(
        name=player_name,
        symbol=PlayerSymbol.X,
        client_id=client_id
    )
    
    room = GameRoom(
        id=room_id,
        players={player_name: player},
        board={},
        current_turn=player_name,
        created_at=time.time()
    )
    
    rooms[room_id] = room
    logger.info(f"Created room {room_id} with player {player_name}")
    return room_id, player

def join_room(room: GameRoom, player_name: str, symbol: str, client_id: str) -> Player:
    """Join an existing game room"""
    if not room.validate_state():
        raise GameStateError("Invalid room state")
        
    if len(room.players) >= 2:
        raise ValueError("Room is full")
        
    if player_name in room.players:
        raise ValueError("Player name already taken")
        
    # Validate symbol
    try:
        player_symbol = PlayerSymbol(symbol)
    except ValueError:
        raise ValueError("Invalid symbol")
        
    # Check if symbol is already taken
    for player in room.players.values():
        if player.symbol == player_symbol:
            raise ValueError("Symbol already taken")
            
    player = Player(
        name=player_name,
        symbol=player_symbol,
        client_id=client_id
    )
    room.players[player_name] = player
    logger.info(f"Player {player_name} joined room {room.id}")
    return player

def get_room_state(room: GameRoom) -> Dict:
    """Get the current state of the room"""
    return {
        "id": room.id,
        "players": {
            name: {
                "name": player.name,
                "symbol": player.symbol.value
            }
            for name, player in room.players.items()
        },
        "board": {
            f"{x},{y}": symbol.value
            for (x, y), symbol in room.board.items()
        },
        "current_turn": room.current_turn,
        "is_game_over": room.is_game_over,
        "winner": room.winner,
        "last_move": room.last_move
    } 
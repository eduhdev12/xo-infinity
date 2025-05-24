from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
from enum import Enum

class PlayerSymbol(Enum):
    X = "X"
    O = "O"

@dataclass
class Player:
    name: str
    symbol: PlayerSymbol
    websocket: any  # Will be set to websockets.WebSocketServerProtocol

@dataclass
class GameRoom:
    room_id: str
    players: Dict[str, Player]  # player_name -> Player
    board: Dict[Tuple[int, int], PlayerSymbol]  # (x, y) -> PlayerSymbol
    current_turn: Optional[str]  # player_name
    is_game_over: bool = False
    winner: Optional[str] = None  # player_name

class GameState:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}  # room_id -> GameRoom
        self.player_rooms: Dict[str, str] = {}  # player_name -> room_id
        self.leaderboard: Dict[str, int] = {}  # player_name -> wins 
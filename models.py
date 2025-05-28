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

@dataclass
class GameRoom:
    room_id: str
    players: Dict[str, Player]
    board: Dict[Tuple[int, int], PlayerSymbol]
    current_turn: Optional[str]
    is_game_over: bool = False
    winner: Optional[str] = None

class GameState:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.player_rooms: Dict[str, str] = {}
        self.leaderboard: Dict[str, int] = {}
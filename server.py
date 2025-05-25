import logging
import time
from typing import Dict, Optional
from network import TCPServer, Message, NetworkError
from game_logic import (
    PlayerSymbol, Player, GameRoom, GameError,
    create_room, join_room, make_move, get_room_state
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.server = TCPServer(host, port)
        self.rooms: Dict[str, GameRoom] = {}
        self.leaderboard: Dict[str, int] = {}
        self._setup_message_handlers()
        
    def _setup_message_handlers(self):
        """Set up message handlers for different message types"""
        self.server.message_handlers = {
            "create_room": self._handle_create_room,
            "join_room": self._handle_join_room,
            "make_move": self._handle_make_move,
            "get_leaderboard": self._handle_get_leaderboard
        }
        
    def _handle_create_room(self, client_id: str, data: Dict):
        """Handle room creation request"""
        try:
            player_name = data["player_name"]
            room_id, player = create_room(self.rooms, player_name, client_id)
            
            self.server.send_message(client_id, Message(
                type="room_created",
                data={
                    "room_id": room_id,
                    "player_name": player_name,
                    "symbol": player.symbol.value
                }
            ))
            
        except Exception as e:
            logger.error(f"Error creating room: {str(e)}")
            self.server.send_message(client_id, Message(
                type="error",
                data={"message": str(e)}
            ))
            
    def _handle_join_room(self, client_id: str, data: Dict):
        """Handle room join request"""
        try:
            room_id = data["room_id"]
            player_name = data["player_name"]
            symbol = data["symbol"]
            
            if room_id not in self.rooms:
                raise ValueError("Room not found")
                
            room = self.rooms[room_id]
            player = join_room(room, player_name, symbol, client_id)
            
            # Send current board state to the new player
            room_state = get_room_state(room)
            logger.info(f"Sending board state to new player: {room_state}")
            self.server.send_message(client_id, Message(
                type="board_state",
                data=room_state
            ))
            
            # Notify both players
            for p in room.players.values():
                if p.client_id:
                    logger.info(f"Notifying player {p.name} about new player join")
                    self.server.send_message(p.client_id, Message(
                        type="player_joined",
                        data={
                            "player": player_name,
                            "current_turn": room.current_turn,
                            "symbol": symbol,
                            "is_my_turn": p.name == room.current_turn
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            self.server.send_message(client_id, Message(
                type="error",
                data={"message": str(e)}
            ))
            
    def _handle_make_move(self, client_id: str, data: Dict):
        """Handle move request"""
        try:
            logger.info(f"Making move: {data}")
            room_id = data["room_id"]
            x = data["x"]
            y = data["y"]
            player_name = data["player_name"]
            
            if room_id not in self.rooms:
                raise ValueError("Room not found")
                
            room = self.rooms[room_id]
            if player_name not in room.players:
                raise ValueError("Player not in room")
                
            player = room.players[player_name]
            if player.client_id != client_id:
                raise ValueError("Invalid client ID")
                
            # Make move
            move_result = make_move(room, player, x, y)
            
            # Get current room state
            room_state = get_room_state(room)
            
            # Notify both players with updated board state
            for p in room.players.values():
                if p.client_id:
                    # Update turn information
                    room_state["is_my_turn"] = p.name == room.current_turn
                    logger.info(f"Sending move result to {p.name}, is_my_turn: {room_state['is_my_turn']}")
                    
                    # Combine room state with move result
                    message_data = {
                        **room_state,
                        "is_win": move_result.get("is_win", False),
                        "is_draw": move_result.get("is_draw", False),
                        "winner": move_result.get("winner"),
                        "winning_positions": move_result.get("winning_positions"),
                        "is_game_over": move_result.get("is_game_over", False)
                    }
                    
                    self.server.send_message(p.client_id, Message(
                        type="move_made",
                        data=message_data
                    ))
                    
            # Update leaderboard if there's a winner
            if move_result.get("is_win"):
                self.leaderboard[player_name] = self.leaderboard.get(player_name, 0) + 1
                # Send leaderboard update
                for p in room.players.values():
                    if p.client_id:
                        self.server.send_message(p.client_id, Message(
                            type="leaderboard_update",
                            data={"leaderboard": self.leaderboard}
                        ))
                        
        except Exception as e:
            logger.error(f"Error making move: {str(e)}")
            self.server.send_message(client_id, Message(
                type="error",
                data={"message": str(e)}
            ))
            
    def _handle_get_leaderboard(self, client_id: str, data: Dict):
        """Handle leaderboard request"""
        try:
            self.server.send_message(client_id, Message(
                type="leaderboard_update",
                data={"leaderboard": self.leaderboard}
            ))
        except Exception as e:
            logger.error(f"Error getting leaderboard: {str(e)}")
            self.server.send_message(client_id, Message(
                type="error",
                data={"message": str(e)}
            ))
            
    def start(self):
        """Start the game server"""
        try:
            self.server.start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.server.stop()
            
if __name__ == "__main__":
    server = GameServer()
    server.start()
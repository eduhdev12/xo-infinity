import asyncio
import json
import websockets
import logging
from typing import Dict, Set, Optional
from game_logic import (
    PlayerSymbol, Player, GameRoom,
    create_room, join_room, make_move, check_win_condition
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.leaderboard: Dict[str, int] = {}
        
    async def handle_client(self, websocket, path):
        """Handle a client connection"""
        try:
            logger.info("New client connected")
            player = None
            room = None
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"Received message: {data}")
                    
                    if data["type"] == "create_room":
                        player_name = data["player_name"]
                        room_id, player = create_room(self.rooms, player_name)
                        player.websocket = websocket
                        await websocket.send(json.dumps({
                            "type": "room_created",
                            "room_id": room_id
                        }))
                        logger.info(f"Room created: {room_id}")
                        
                    elif data["type"] == "join_room":
                        room_id = data["room_id"]
                        player_name = data["player_name"]
                        symbol = data["symbol"]
                        
                        if room_id not in self.rooms:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Room not found"
                            }))
                            continue
                            
                        room = self.rooms[room_id]
                        player = join_room(room, player_name, symbol)
                        player.websocket = websocket
                        
                        # Send current board state to the new player
                        await websocket.send(json.dumps({
                            "type": "board_state",
                            "board": room.board,
                            "current_turn": room.current_turn,
                            "is_game_over": room.is_game_over,
                            "winner": room.winner
                        }))
                        
                        # Notify both players
                        for p in room.players.values():
                            if p.websocket:
                                await p.websocket.send(json.dumps({
                                    "type": "player_joined",
                                    "player": player_name,
                                    "current_turn": room.current_turn,
                                    "symbol": symbol
                                }))
                        logger.info(f"Player {player_name} joined room {room_id}")
                        
                    elif data["type"] == "make_move":
                        if not player or not room:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Not in a game"
                            }))
                            continue
                            
                        x = data["x"]
                        y = data["y"]
                        player_name = data["player_name"]
                        
                        # Validate move
                        if player_name != room.current_turn:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Not your turn"
                            }))
                            continue
                            
                        if (x, y) in room.board:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Position already taken"
                            }))
                            continue
                            
                        # Make move
                        move_result = make_move(room, player, x, y)
                        if not move_result["success"]:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": move_result["message"]
                            }))
                            continue
                            
                        # Check win condition
                        win_result = check_win_condition(room, x, y)
                        if win_result["is_win"]:
                            room.is_game_over = True
                            room.winner = player_name
                            # Update leaderboard
                            self.leaderboard[player_name] = self.leaderboard.get(player_name, 0) + 1
                            
                        # Notify both players with full board state
                        for p in room.players.values():
                            if p.websocket:
                                await p.websocket.send(json.dumps({
                                    "type": "move_made",
                                    "player": player_name,
                                    "x": x,
                                    "y": y,
                                    "symbol": player.symbol,
                                    "current_turn": room.current_turn,
                                    "is_game_over": room.is_game_over,
                                    "winner": room.winner,
                                    "board": room.board  # Send full board state
                                }))
                            
                        # Send leaderboard update
                        for p in room.players.values():
                            if p.websocket:
                                await p.websocket.send(json.dumps({
                                    "type": "leaderboard_update",
                                    "leaderboard": self.leaderboard
                                }))
                            
                except json.JSONDecodeError:
                    logger.error("Invalid JSON message")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid message format"
                    }))
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
            if player and room:
                # Remove player from room
                if player.name in room.players:
                    del room.players[player.name]
                # Notify other player
                for p in room.players.values():
                    if p.websocket:
                        asyncio.create_task(p.websocket.send(json.dumps({
                            "type": "player_disconnected",
                            "player": player.name
                        })))
                # Clean up empty rooms
                if not room.players:
                    del self.rooms[room.id]
        except Exception as e:
            logger.error(f"Error handling client: {str(e)}")

async def main():
    server = GameServer()
    async with websockets.serve(server.handle_client, "localhost", 8765):
        logger.info("Server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
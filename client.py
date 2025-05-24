import asyncio
import json
import customtkinter as ctk
import websockets
from PIL import Image, ImageDraw
from typing import Dict, Optional, Tuple
import threading
import queue
import logging
import math

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameClient:
    def __init__(self):
        self.ws = None
        self.player_name = ""
        self.room_id = ""
        self.symbol = ""
        self.current_turn = ""
        self.board: Dict[Tuple[int, int], str] = {}
        self.is_game_over = False
        self.winner = None
        self.leaderboard: Dict[str, int] = {}
        self.message_queue = queue.Queue()
        self.loop = None
        self.connection_thread = None
        
        # Board view settings
        self.cell_size = 50
        self.offset_x = 250
        self.offset_y = 250
        self.zoom_level = 1.0
        self.is_dragging = False
        self.last_x = 0
        self.last_y = 0
        
        # GUI setup
        self.setup_gui()
        logger.info("Game client initialized")
        
    def setup_gui(self):
        self.root = ctk.CTk()
        self.root.title("Infinite Tic-Tac-Toe")
        self.root.geometry("1200x800")
        
        # Configure grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=3)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Left panel for controls
        self.left_panel = ctk.CTkFrame(self.root)
        self.left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Player info
        self.name_label = ctk.CTkLabel(self.left_panel, text="Enter your name:")
        self.name_label.pack(pady=5)
        self.name_entry = ctk.CTkEntry(self.left_panel)
        self.name_entry.pack(pady=5)
        
        # Room controls
        self.create_room_btn = ctk.CTkButton(
            self.left_panel, 
            text="Create Room",
            command=self.create_room
        )
        self.create_room_btn.pack(pady=5)
        
        self.room_label = ctk.CTkLabel(self.left_panel, text="Room ID:")
        self.room_label.pack(pady=5)
        self.room_entry = ctk.CTkEntry(self.left_panel)
        self.room_entry.pack(pady=5)
        
        self.symbol_label = ctk.CTkLabel(self.left_panel, text="Choose symbol:")
        self.symbol_label.pack(pady=5)
        self.symbol_var = ctk.StringVar(value="X")
        self.symbol_x = ctk.CTkRadioButton(
            self.left_panel, 
            text="X", 
            variable=self.symbol_var, 
            value="X"
        )
        self.symbol_x.pack(pady=2)
        self.symbol_o = ctk.CTkRadioButton(
            self.left_panel, 
            text="O", 
            variable=self.symbol_var, 
            value="O"
        )
        self.symbol_o.pack(pady=2)
        
        self.join_room_btn = ctk.CTkButton(
            self.left_panel, 
            text="Join Room",
            command=self.join_room
        )
        self.join_room_btn.pack(pady=5)
        
        # Game status
        self.status_label = ctk.CTkLabel(
            self.left_panel, 
            text="Status: Not connected"
        )
        self.status_label.pack(pady=5)
        
        # Leaderboard
        self.leaderboard_label = ctk.CTkLabel(
            self.left_panel, 
            text="Leaderboard:"
        )
        self.leaderboard_label.pack(pady=5)
        self.leaderboard_text = ctk.CTkTextbox(
            self.left_panel, 
            height=100
        )
        self.leaderboard_text.pack(pady=5)
        
        # Right panel for game board
        self.right_panel = ctk.CTkFrame(self.root)
        self.right_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Canvas for the infinite board
        self.canvas = ctk.CTkCanvas(
            self.right_panel,
            bg="white",
            width=800,
            height=800
        )
        self.canvas.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux scroll down
        self.canvas.bind("<Configure>", self.on_canvas_configure)  # Handle resizing
        
        # Initialize canvas size
        self.canvas_width = 800
        self.canvas_height = 800
        
        # Schedule initial grid drawing after window is loaded
        self.root.after(200, self.draw_grid)
        
    def on_canvas_configure(self, event):
        """Handle canvas resize events"""
        self.canvas_width = event.width
        self.canvas_height = event.height
        self.draw_grid()
        
    def draw_grid(self):
        """Draw the infinite grid"""
        self.canvas.delete("all")  # Clear the entire canvas
        
        # Get actual canvas dimensions
        width = self.canvas_width
        height = self.canvas_height
        
        if width <= 1 or height <= 1:  # Canvas not yet properly sized
            width = self.canvas.winfo_width() or 800
            height = self.canvas.winfo_height() or 800
        
        # Calculate grid boundaries
        start_x = math.floor(-self.offset_x / (self.cell_size * self.zoom_level))
        end_x = math.ceil((width - self.offset_x) / (self.cell_size * self.zoom_level))
        start_y = math.floor(-self.offset_y / (self.cell_size * self.zoom_level))
        end_y = math.ceil((height - self.offset_y) / (self.cell_size * self.zoom_level))
        
        # Draw vertical lines
        for x in range(start_x, end_x + 1):
            canvas_x = self.offset_x + x * self.cell_size * self.zoom_level
            self.canvas.create_line(
                canvas_x, 0, canvas_x, height,
                fill="gray", width=1, tags="grid"
            )
        
        # Draw horizontal lines
        for y in range(start_y, end_y + 1):
            canvas_y = self.offset_y + y * self.cell_size * self.zoom_level
            self.canvas.create_line(
                0, canvas_y, width, canvas_y,
                fill="gray", width=1, tags="grid"
            )
        
        # Draw all symbols from the board state
        for (x, y), symbol in self.board.items():
            self.draw_symbol(x, y, symbol)
    
    def draw_symbol(self, x: int, y: int, symbol: str):
        """Draw a symbol on the canvas"""
        try:
            # Convert board coordinates to canvas coordinates
            canvas_x = self.offset_x + x * self.cell_size * self.zoom_level
            canvas_y = self.offset_y + y * self.cell_size * self.zoom_level
            size = 15 * self.zoom_level
            
            # Draw the symbol
            if symbol == "X":
                self.canvas.create_line(
                    canvas_x - size, canvas_y - size,
                    canvas_x + size, canvas_y + size,
                    fill="blue", width=2 * self.zoom_level,
                    tags=f"symbol_{x}_{y}"
                )
                self.canvas.create_line(
                    canvas_x + size, canvas_y - size,
                    canvas_x - size, canvas_y + size,
                    fill="blue", width=2 * self.zoom_level,
                    tags=f"symbol_{x}_{y}"
                )
            else:  # O
                self.canvas.create_oval(
                    canvas_x - size, canvas_y - size,
                    canvas_x + size, canvas_y + size,
                    outline="red", width=2 * self.zoom_level,
                    tags=f"symbol_{x}_{y}"
                )
            logger.info(f"Drew {symbol} at ({x}, {y})")
        except Exception as e:
            logger.error(f"Error drawing symbol: {str(e)}")
    
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        # Record position for potential move or drag operation
        self.is_dragging = True
        self.last_x = event.x
        self.last_y = event.y
        
        # Calculate board coordinates for potential move
        x = int(round((event.x - self.offset_x) / (self.cell_size * self.zoom_level)))
        y = int(round((event.y - self.offset_y) / (self.cell_size * self.zoom_level)))
        
        # Store the coordinates for potential move on release
        self.potential_move_x = x
        self.potential_move_y = y
    
    def on_canvas_drag(self, event):
        """Handle canvas dragging for panning"""
        if self.is_dragging:
            dx = event.x - self.last_x
            dy = event.y - self.last_y
            
            # If we've moved more than a small threshold, consider it a drag rather than a click
            if abs(dx) > 5 or abs(dy) > 5:
                self.offset_x += dx
                self.offset_y += dy
                self.last_x = event.x
                self.last_y = event.y
                self.draw_grid()
    
    def on_canvas_release(self, event):
        """Handle canvas release after dragging"""
        # Only consider it a move if we haven't dragged much
        if self.is_dragging and abs(event.x - self.last_x) < 5 and abs(event.y - self.last_y) < 5:
            self.make_move(self.potential_move_x, self.potential_move_y)
        
        self.is_dragging = False
    
    def make_move(self, x, y):
        """Process a move at board coordinates (x, y)"""
        if not self.ws or self.is_game_over:
            logger.info("Cannot make move: No connection or game is over")
            return
            
        if self.current_turn != self.player_name:
            logger.info(f"Cannot make move: Not your turn (current turn: {self.current_turn}, you: {self.player_name})")
            return
            
        logger.info(f"Attempting move at ({x}, {y})")
        
        # Check if the position is already taken
        if (x, y) in self.board:
            logger.info("Position already taken")
            return
            
        # Send move to server
        if self.loop and self.ws:
            try:
                asyncio.run_coroutine_threadsafe(self.send_move(x, y), self.loop)
                logger.info(f"Move sent to server: ({x}, {y})")
            except Exception as e:
                logger.error(f"Error sending move: {str(e)}")
                self.status_label.configure(text=f"Error sending move: {str(e)}")
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        # Get mouse position for zooming around this point
        mouse_x = event.x
        mouse_y = event.y
        
        # Convert to board coordinates before zoom
        board_x = (mouse_x - self.offset_x) / (self.cell_size * self.zoom_level)
        board_y = (mouse_y - self.offset_y) / (self.cell_size * self.zoom_level)
        
        # Determine zoom direction
        old_zoom = self.zoom_level
        if hasattr(event, 'delta'):  # Windows
            if event.delta < 0:  # Zoom out
                self.zoom_level = max(0.1, self.zoom_level * 0.9)
            else:  # Zoom in
                self.zoom_level = min(2.0, self.zoom_level * 1.1)
        elif event.num == 5:  # Linux scroll down
            self.zoom_level = max(0.1, self.zoom_level * 0.9)
        elif event.num == 4:  # Linux scroll up
            self.zoom_level = min(2.0, self.zoom_level * 1.1)
        
        # Adjust offset to zoom around mouse position
        zoom_ratio = self.zoom_level / old_zoom
        self.offset_x = mouse_x - board_x * self.cell_size * self.zoom_level
        self.offset_y = mouse_y - board_y * self.cell_size * self.zoom_level
        
        self.draw_grid()
    
    async def send_move(self, x: int, y: int):
        """Send a move to the server"""
        if not self.ws:
            logger.error("Cannot send move: No WebSocket connection")
            return
            
        try:
            message = {
                "type": "make_move",
                "player_name": self.player_name,
                "x": x,
                "y": y
            }
            logger.info(f"Sending move: {message}")
            await self.ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error in send_move: {str(e)}")
            self.status_label.configure(text=f"Error sending move: {str(e)}")
    
    def create_room(self):
        self.player_name = self.name_entry.get().strip()
        if not self.player_name:
            self.status_label.configure(text="Status: Please enter your name")
            return
            
        logger.info(f"Creating room for player: {self.player_name}")
        self.start_connection("create")
    
    def join_room(self):
        self.player_name = self.name_entry.get().strip()
        self.room_id = self.room_entry.get().strip()
        self.symbol = self.symbol_var.get()
        
        if not all([self.player_name, self.room_id, self.symbol]):
            self.status_label.configure(text="Status: Please fill all fields")
            return
            
        logger.info(f"Joining room {self.room_id} as {self.player_name} with symbol {self.symbol}")
        self.start_connection("join")

    def start_connection(self, connection_type: str):
        """Start the connection in a new thread"""
        if self.connection_thread and self.connection_thread.is_alive():
            logger.warning("Connection already in progress")
            return

        self.connection_thread = threading.Thread(
            target=self.run_async_connection,
            args=(connection_type,),
            daemon=True
        )
        self.connection_thread.start()
    
    def run_async_connection(self, connection_type: str):
        """Run the async connection in a new event loop"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            if connection_type == "create":
                self.loop.run_until_complete(self.connect_and_create_room())
            else:
                self.loop.run_until_complete(self.connect_and_join_room())
        except Exception as e:
            logger.error(f"Connection error in thread: {str(e)}")
            self.root.after(0, lambda: self.status_label.configure(text=f"Status: Error - {str(e)}"))
    
    async def connect_and_create_room(self):
        try:
            logger.info("Connecting to server...")
            async with websockets.connect("ws://localhost:8765") as websocket:
                self.ws = websocket
                logger.info("Connected to server")
                message = {
                    "type": "create_room",
                    "player_name": self.player_name
                }
                logger.info(f"Sending create room request: {message}")
                await websocket.send(json.dumps(message))
                
                while True:
                    try:
                        message = await websocket.recv()
                        logger.info(f"Received message: {message}")
                        self.message_queue.put(message)
                        self.root.after(100, self.process_messages)
                    except websockets.exceptions.ConnectionClosed:
                        logger.error("Connection closed by server")
                        self.root.after(0, lambda: self.status_label.configure(text="Status: Connection closed"))
                        break
                    except Exception as e:
                        logger.error(f"Error receiving message: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self.root.after(0, lambda: self.status_label.configure(text=f"Status: Error - {str(e)}"))
        finally:
            self.ws = None
    
    async def connect_and_join_room(self):
        try:
            logger.info("Connecting to server...")
            async with websockets.connect("ws://localhost:8765") as websocket:
                self.ws = websocket
                logger.info("Connected to server")
                message = {
                    "type": "join_room",
                    "player_name": self.player_name,
                    "room_id": self.room_id,
                    "symbol": self.symbol
                }
                logger.info(f"Sending join room request: {message}")
                await websocket.send(json.dumps(message))
                
                while True:
                    try:
                        message = await websocket.recv()
                        logger.info(f"Received message: {message}")
                        self.message_queue.put(message)
                        self.root.after(100, self.process_messages)
                    except websockets.exceptions.ConnectionClosed:
                        logger.error("Connection closed by server")
                        self.root.after(0, lambda: self.status_label.configure(text="Status: Connection closed"))
                        break
                    except Exception as e:
                        logger.error(f"Error receiving message: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self.root.after(0, lambda: self.status_label.configure(text=f"Status: Error - {str(e)}"))
        finally:
            self.ws = None

    def process_messages(self):
        """Process messages from the server"""
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                data = json.loads(message)
                logger.info(f"Processing message: {data}")
                
                if data["type"] == "error":
                    self.status_label.configure(text=f"Status: Error - {data['message']}")
                elif data["type"] == "room_created":
                    self.room_id = data["room_id"]
                    self.room_entry.delete(0, "end")
                    self.room_entry.insert(0, self.room_id)
                    self.status_label.configure(text="Status: Room created")
                elif data["type"] == "board_state":
                    # Update the entire board state
                    self.board = data["board"]
                    self.current_turn = data["current_turn"]
                    self.is_game_over = data["is_game_over"]
                    self.winner = data["winner"]
                    # Redraw the entire board
                    self.draw_grid()
                    # Update status
                    if self.is_game_over:
                        self.status_label.configure(text=f"Status: Game Over! Winner: {self.winner}")
                    else:
                        self.status_label.configure(text=f"Status: {self.current_turn}'s turn")
                elif data["type"] == "player_joined":
                    self.status_label.configure(
                        text=f"Status: {data['player']} joined the game"
                    )
                    self.current_turn = data["current_turn"]
                    # Store our symbol from the first player
                    if "symbol" in data and data["player"] == self.player_name:
                        self.symbol = data["symbol"]
                elif data["type"] == "move_made":
                    # Update the entire board state
                    self.board = data["board"]
                    self.current_turn = data["current_turn"]
                    self.is_game_over = data["is_game_over"]
                    self.winner = data["winner"]
                    
                    # Redraw the entire board
                    self.draw_grid()
                    
                    # Update status
                    if self.is_game_over:
                        self.status_label.configure(text=f"Status: Game Over! Winner: {self.winner}")
                    else:
                        self.status_label.configure(text=f"Status: {self.current_turn}'s turn")
                elif data["type"] == "leaderboard_update":
                    self.leaderboard = data["leaderboard"]
                    self.update_leaderboard()
                elif data["type"] == "player_disconnected":
                    self.status_label.configure(
                        text=f"Status: {data['player']} disconnected"
                    )
                    self.is_game_over = True
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            self.status_label.configure(text=f"Status: Error processing message - {str(e)}")
    
    def update_leaderboard(self):
        self.leaderboard_text.delete("1.0", "end")
        for player, wins in sorted(
            self.leaderboard.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            self.leaderboard_text.insert("end", f"{player}: {wins} wins\n")
    
    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
        finally:
            if self.loop:
                self.loop.stop()
            if self.ws:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

if __name__ == "__main__":
    client = GameClient()
    client.run()
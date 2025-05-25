import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Dict, Optional, Tuple, Callable
from network import TCPClient, Message, NetworkError
from game_logic import PlayerSymbol
import math

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameClient:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.client = TCPClient(host, port)
        self.setup_message_handlers()
        self.current_room: Optional[str] = None
        self.player_name: Optional[str] = None
        self.player_symbol: Optional[PlayerSymbol] = None
        self.is_my_turn = False
        self.game_over = False
        self.board: Dict[Tuple[int, int], str] = {}
        
    def setup_message_handlers(self):
        """Set up message handlers for different message types"""
        self.client.message_handlers = {
            "room_created": self._handle_room_created,
            "board_state": self._handle_board_state,
            "player_joined": self._handle_player_joined,
            "move_made": self._handle_move_made,
            "error": self._handle_error,
            "leaderboard_update": self._handle_leaderboard_update
        }
        
    def connect(self):
        """Connect to the server"""
        try:
            self.client.connect()
            logger.info("Connected to server successfully")
            return True
        except NetworkError as e:
            logger.error(f"Failed to connect: {str(e)}")
            return False
            
    def disconnect(self):
        """Disconnect from the server"""
        self.client.disconnect()
        
    def create_room(self, player_name: str):
        """Create a new game room"""
        logger.info(f"Creating room for player: {player_name}")
        self.player_name = player_name
        self.client.send_message(Message(
            type="create_room",
            data={"player_name": player_name}
        ))
        
    def join_room(self, room_id: str, player_name: str, symbol: str):
        """Join an existing game room"""
        logger.info(f"Joining room {room_id} as {player_name} with symbol {symbol}")
        self.player_name = player_name
        self.player_symbol = PlayerSymbol(symbol)
        self.client.send_message(Message(
            type="join_room",
            data={
                "room_id": room_id,
                "player_name": player_name,
                "symbol": symbol
            }
        ))
        
    def make_move(self, x: int, y: int):
        """Make a move in the game"""
        logger.info(f"Attempting move at ({x}, {y}) - Room: {self.current_room}, Turn: {self.is_my_turn}, Symbol: {self.player_symbol}")
        
        if self.game_over:
            logger.info("Cannot make move: game is over")
            return
            
        if not self.is_my_turn:
            logger.info("Cannot make move: not my turn")
            return
            
        if not self.current_room or not self.player_name:
            logger.error("Cannot make move: not in a room")
            return
            
        try:
            self.client.send_message(Message(
                type="make_move",
                data={
                    "room_id": self.current_room,
                    "player_name": self.player_name,
                    "x": x,
                    "y": y
                }
            ))
            logger.info(f"Move message sent: ({x}, {y})")
        except Exception as e:
            logger.error(f"Error sending move: {str(e)}")
            
    def get_leaderboard(self):
        """Request the current leaderboard"""
        self.client.send_message(Message(
            type="get_leaderboard",
            data={}
        ))
        
    def _handle_room_created(self, data: Dict):
        """Handle room created response"""
        logger.info(f"Room created: {data}")
        self.current_room = data["room_id"]
        self.player_symbol = PlayerSymbol(data["symbol"])
        logger.info(f"Player symbol set to: {self.player_symbol}")
        if hasattr(self, 'on_room_created'):
            self.on_room_created(data)
            
    def _handle_board_state(self, data: Dict):
        """Handle board state update"""
        logger.info(f"Board state update: {data}")
        self.current_room = data["id"]
        self.is_my_turn = data.get("is_my_turn", False)
        self.game_over = data["is_game_over"]
        self.board = {
            tuple(map(int, pos.split(','))): symbol
            for pos, symbol in data["board"].items()
        }
        logger.info(f"Updated board state - Turn: {self.is_my_turn}, Game over: {self.game_over}")
        if hasattr(self, 'on_board_state'):
            self.on_board_state(data)
            
    def _handle_player_joined(self, data: Dict):
        """Handle player joined notification"""
        logger.info(f"Player joined: {data}")
        self.is_my_turn = data.get("is_my_turn", False)
        logger.info(f"Updated turn state after player join: {self.is_my_turn}")
        if hasattr(self, 'on_player_joined'):
            self.on_player_joined(data)
            
    def _handle_move_made(self, data: Dict):
        """Handle move made notification"""
        logger.info(f"Move made: {data}")
        self.is_my_turn = data.get("is_my_turn", False)
        self.game_over = data["is_game_over"]
        self.board = {
            tuple(map(int, pos.split(','))): symbol
            for pos, symbol in data["board"].items()
        }
        logger.info(f"Updated game state - Turn: {self.is_my_turn}, Game over: {self.game_over}")
        if hasattr(self, 'on_move_made'):
            self.on_move_made(data)
            
    def _handle_error(self, data: Dict):
        """Handle error message"""
        logger.error(f"Received error: {data}")
        if hasattr(self, 'on_error'):
            self.on_error(data["message"])
            
    def _handle_leaderboard_update(self, data: Dict):
        """Handle leaderboard update"""
        logger.info(f"Leaderboard update: {data}")
        if hasattr(self, 'on_leaderboard_update'):
            self.on_leaderboard_update(data["leaderboard"])

class GameUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("XO Infinity")
        self.game_client = GameClient()
        
        # Canvas settings
        self.cell_size = 50
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_level = 1.0
        self.is_dragging = False
        self.last_x = 0
        self.last_y = 0
        self.potential_move_x = 0
        self.potential_move_y = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the game UI"""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        # Left panel for controls
        self.left_panel = ttk.Frame(self.main_frame)
        self.left_panel.grid(row=0, column=0, rowspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Player info
        ttk.Label(self.left_panel, text="Player Name:").pack(pady=5)
        self.player_name_var = tk.StringVar()
        ttk.Entry(self.left_panel, textvariable=self.player_name_var).pack(pady=5)
        
        ttk.Button(self.left_panel, text="Create Room", command=self.create_room).pack(pady=5)
        
        # Room join
        ttk.Label(self.left_panel, text="Room ID:").pack(pady=5)
        self.room_id_var = tk.StringVar()
        ttk.Entry(self.left_panel, textvariable=self.room_id_var).pack(pady=5)
        
        ttk.Label(self.left_panel, text="Symbol:").pack(pady=5)
        self.symbol_var = tk.StringVar(value="O")
        ttk.Radiobutton(self.left_panel, text="X", variable=self.symbol_var, value="X").pack()
        ttk.Radiobutton(self.left_panel, text="O", variable=self.symbol_var, value="O").pack()
        
        ttk.Button(self.left_panel, text="Join Room", command=self.join_room).pack(pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Welcome to XO Infinity!")
        ttk.Label(self.left_panel, textvariable=self.status_var).pack(pady=5)
        
        # Leaderboard
        ttk.Label(self.left_panel, text="Leaderboard").pack(pady=5)
        self.leaderboard_text = tk.Text(self.left_panel, height=5, width=20)
        self.leaderboard_text.pack(pady=5)
        
        # Canvas for the infinite board
        self.canvas_frame = ttk.Frame(self.main_frame)
        self.canvas_frame.grid(row=0, column=1, rowspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg="white",
            width=800,
            height=800
        )
        self.canvas.pack(expand=True, fill="both")
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux scroll down
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Set up message handlers
        self.game_client.on_room_created = self.handle_room_created
        self.game_client.on_board_state = self.handle_board_state
        self.game_client.on_player_joined = self.handle_player_joined
        self.game_client.on_move_made = self.handle_move_made
        self.game_client.on_error = self.handle_error
        self.game_client.on_leaderboard_update = self.handle_leaderboard_update
        
        # Connect to server
        if not self.game_client.connect():
            messagebox.showerror("Error", "Failed to connect to server")
            self.root.quit()
            
        # Initial grid drawing
        self.draw_grid()
        
    def create_room(self):
        """Create a new game room"""
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showerror("Error", "Please enter a player name")
            return
            
        logger.info(f"Creating room for player: {player_name}")
        self.game_client.create_room(player_name)
        
    def join_room(self):
        """Join an existing game room"""
        room_id = self.room_id_var.get().strip()
        player_name = self.player_name_var.get().strip()
        symbol = self.symbol_var.get()
        
        if not room_id or not player_name:
            messagebox.showerror("Error", "Please enter room ID and player name")
            return
            
        logger.info(f"Joining room {room_id} as {player_name} with symbol {symbol}")
        self.game_client.join_room(room_id, player_name, symbol)
        
    def on_canvas_configure(self, event):
        """Handle canvas resize events"""
        self.draw_grid()
        
    def draw_grid(self):
        """Draw the infinite grid"""
        self.canvas.delete("all")
        
        # Get canvas dimensions
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            width = 800
            height = 800
        
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
                fill="gray", width=1
            )
            # Draw coordinates
            if x % 5 == 0:  # Show coordinates every 5 cells
                self.canvas.create_text(
                    canvas_x, 10,
                    text=str(x),
                    fill="blue"
                )
        
        # Draw horizontal lines
        for y in range(start_y, end_y + 1):
            canvas_y = self.offset_y + y * self.cell_size * self.zoom_level
            self.canvas.create_line(
                0, canvas_y, width, canvas_y,
                fill="gray", width=1
            )
            # Draw coordinates
            if y % 5 == 0:  # Show coordinates every 5 cells
                self.canvas.create_text(
                    10, canvas_y,
                    text=str(y),
                    fill="blue"
                )
        
        # Draw symbols
        for (x, y), symbol in self.game_client.board.items():
            self.draw_symbol(x, y, symbol)
            
    def draw_symbol(self, x: int, y: int, symbol: str):
        """Draw a symbol on the canvas"""
        # Calculate the center of the cell
        canvas_x = self.offset_x + (x + 0.5) * self.cell_size * self.zoom_level
        canvas_y = self.offset_y + (y + 0.5) * self.cell_size * self.zoom_level
        # Make symbol size relative to cell size
        size = (self.cell_size * self.zoom_level * 0.3)  # 30% of cell size
        
        if symbol == "X":
            self.canvas.create_line(
                canvas_x - size, canvas_y - size,
                canvas_x + size, canvas_y + size,
                fill="blue", width=2 * self.zoom_level
            )
            self.canvas.create_line(
                canvas_x + size, canvas_y - size,
                canvas_x - size, canvas_y + size,
                fill="blue", width=2 * self.zoom_level
            )
        elif symbol == "O":
            self.canvas.create_oval(
                canvas_x - size, canvas_y - size,
                canvas_x + size, canvas_y + size,
                outline="red", width=2 * self.zoom_level
            )
            
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        self.is_dragging = True
        self.last_x = event.x
        self.last_y = event.y
        
        # Calculate board coordinates, snapping to cell centers
        x = int(round((event.x - self.offset_x) / (self.cell_size * self.zoom_level) - 0.5))
        y = int(round((event.y - self.offset_y) / (self.cell_size * self.zoom_level) - 0.5))
        
        # Store coordinates for potential move
        self.potential_move_x = x
        self.potential_move_y = y
        
    def on_canvas_drag(self, event):
        """Handle canvas dragging for panning"""
        if self.is_dragging:
            dx = event.x - self.last_x
            dy = event.y - self.last_y
            
            # If we've moved more than a small threshold, consider it a drag
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
        
    def handle_room_created(self, data: Dict):
        """Handle room created response"""
        logger.info(f"Room created: {data}")
        self.status_var.set(f"Room created! Room ID: {data['room_id']}")
        self.room_id_var.set(data['room_id'])
        
    def handle_board_state(self, data: Dict):
        """Handle board state update"""
        logger.info(f"UI handling board state: {data}")
        # Update status
        if data["is_game_over"]:
            if data["winner"]:
                self.status_var.set(f"Game over! {data['winner']} wins!")
            else:
                self.status_var.set("Game over! It's a draw!")
        else:
            current_turn = data["current_turn"]
            is_my_turn = data.get("is_my_turn", False)
            self.status_var.set(f"Current turn: {current_turn} {'(Your turn!)' if is_my_turn else ''}")
            
        # Redraw the board
        self.draw_grid()
        
    def handle_player_joined(self, data: Dict):
        """Handle player joined notification"""
        logger.info(f"Player joined: {data}")
        self.status_var.set(f"Player {data['player']} joined the game!")
        
    def handle_move_made(self, data: Dict):
        """Handle move made notification"""
        logger.info(f"UI handling move made: {data}")
        
        # Update game state
        self.game_client.is_my_turn = data.get("is_my_turn", False)
        self.game_client.game_over = data.get("is_game_over", False)
        
        # Update status
        if data.get("is_game_over"):
            if data.get("is_win"):
                winner = data.get("winner")
                self.status_var.set(f"Game over! {winner} wins!")
                # Highlight winning positions
                if "winning_positions" in data:
                    for x, y in data["winning_positions"]:
                        self.highlight_cell(x, y)
            elif data.get("is_draw"):
                self.status_var.set("Game over! It's a draw!")
        else:
            current_turn = data.get("current_turn", "")
            is_my_turn = data.get("is_my_turn", False)
            self.status_var.set(f"Current turn: {current_turn} {'(Your turn!)' if is_my_turn else ''}")
            
        # Redraw the board
        self.draw_grid()
        
        # Request leaderboard update
        self.game_client.get_leaderboard()
        
    def highlight_cell(self, x: int, y: int):
        """Highlight a cell to show winning positions"""
        # Calculate cell coordinates
        canvas_x = self.offset_x + x * self.cell_size * self.zoom_level
        canvas_y = self.offset_y + y * self.cell_size * self.zoom_level
        
        # Create a highlight rectangle
        self.canvas.create_rectangle(
            canvas_x, canvas_y,
            canvas_x + self.cell_size * self.zoom_level,
            canvas_y + self.cell_size * self.zoom_level,
            fill="yellow", stipple="gray50",  # Semi-transparent yellow
            tags="highlight"
        )
        
    def handle_error(self, message: str):
        """Handle error message"""
        logger.error(f"Error: {message}")
        messagebox.showerror("Error", message)
        
    def handle_leaderboard_update(self, leaderboard: Dict[str, int]):
        """Handle leaderboard update"""
        logger.info(f"Leaderboard update: {leaderboard}")
        self.leaderboard_text.delete(1.0, tk.END)
        for player, score in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True):
            self.leaderboard_text.insert(tk.END, f"{player}: {score}\n")
            
    def make_move(self, x: int, y: int):
        """Make a move in the game by delegating to the game client"""
        self.game_client.make_move(x, y)
            
    def run(self):
        """Run the game UI"""
        self.root.mainloop()
        
if __name__ == "__main__":
    root = tk.Tk()
    game = GameUI(root)
    game.run()
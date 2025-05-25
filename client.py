import socket
import threading
import pickle
import math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext

# Constante locale dacă game_logic.py nu este accesibil
PLAYER_X = 1
PLAYER_O = 2


class GameClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name = ""
        self.room_id = ""
        self.player_symbol = None
        self.board = {}
        self.is_ready = False
        self.is_my_turn = False
        self.game_active = False

        self.cell_size = 25
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_level = 1.0
        self.is_dragging = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.drag_threshold = 5  # pixeli pentru a determina dacă e click sau drag

        self.root = tk.Tk()
        self.root.title("Amoba Game")
        self.root.geometry("800x850")
        self.root.resizable(True, True)

        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, font=('Arial', 10))
        self.style.configure("TEntry", padding=6)

        self.chat_frame = ttk.Frame(self.root)
        self.chat_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.chat_area = scrolledtext.ScrolledText(self.chat_frame, height=8, state='disabled', wrap=tk.WORD)
        self.chat_area.pack(fill='both', expand=True)

        self.input_frame = ttk.Frame(self.root)
        self.input_frame.pack(fill='x', padx=10, pady=5)

        self.entry = ttk.Entry(self.input_frame)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind("<Return>", self.send_chat)

        self.send_btn = ttk.Button(self.input_frame, text="Trimite", command=self.send_chat)
        self.send_btn.pack(side='right', padx=(5, 0))

        self.game_frame = ttk.Frame(self.root)
        self.game_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.control_frame = ttk.Frame(self.game_frame)
        self.control_frame.pack(fill='x', pady=5)

        self.ready_btn = ttk.Button(self.control_frame, text="✅ Sunt gata", command=self.send_ready)
        self.ready_btn.pack(side='left', padx=(0, 10))

        self.players_listbox = tk.Listbox(self.control_frame, height=2, width=30)
        self.players_listbox.pack(side='left', fill='x', expand=True)

        self.canvas = tk.Canvas(self.game_frame, bg="white", highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        # Variabile pentru drag detection
        self.mouse_press_x = 0
        self.mouse_press_y = 0
        self.has_dragged = False

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.info_bar = ttk.Label(self.root, text="Conectare...", relief=tk.SUNKEN)
        self.info_bar.pack(fill='x', padx=10, pady=5)

        self.connect()

    def update_info_bar(self, text):
        self.info_bar.config(text=text)

    def connect(self):
        self.name = simpledialog.askstring("Nume", "Introdu numele tău:", parent=self.root)
        if not self.name:
            self.name = "Player_" + str(id(self) % 1000)

        try:
            self.sock.connect(("localhost", 8765))
            self.sock.sendall(self.name.encode("utf-8"))
            self.update_info_bar(f"Conectat ca {self.name}")
        except ConnectionError:
            messagebox.showerror("Eroare", "Nu mă pot conecta la server", parent=self.root)
            self.root.destroy()
            return

        choice = messagebox.askquestion("Creează sau Alătură-te", "Vrei să creezi o cameră nouă?", parent=self.root)
        if choice == "yes":
            self.sock.sendall(b"CREATE")
        else:
            room_id = simpledialog.askstring("Room ID", "Introdu ID-ul camerei:", parent=self.root)
            if room_id:
                self.room_id = room_id
                self.sock.sendall(f"JOIN {room_id}".encode("utf-8"))
            else:
                self.sock.sendall(b"CREATE")

        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                msg = pickle.loads(data)
                self.root.after(0, self.handle_message, msg)
            except Exception as e:
                print(f"[CLIENT {self.name}] Error in receive loop: {e}")
                self.root.after(0, self.show_error, "Conexiunea cu serverul s-a pierdut")
                break
        self.sock.close()
        self.root.after(0, self.update_info_bar, "Deconectat de la server")

    def handle_message(self, msg):
        print(f"[CLIENT {self.name}] Received msg: {msg['type']}")

        if msg["type"] == "room_created":
            self.room_id = msg["room_id"]
            self.player_symbol = msg["player"]
            self.show_info(f"Camera creată: {self.room_id}")
            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | Așteaptă adversarul")

        elif msg["type"] == "room_joined":
            self.room_id = msg["room_id"]
            self.player_symbol = msg["player"]
            self.show_info(f"Te-ai alăturat camerei: {self.room_id}")
            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | Așteaptă start joc")

        elif msg["type"] == "room_info":
            self.players_listbox.delete(0, tk.END)
            for p_info in msg["players_info"]:
                status = "✓" if p_info["is_ready"] else "○"
                symbol_display = 'X' if p_info['symbol'] == PLAYER_X else ('O' if p_info['symbol'] == PLAYER_O else '?')
                self.players_listbox.insert(tk.END, f"{status} {p_info['name']} ({symbol_display})")

        elif msg["type"] == "chat":
            self.append_chat(f"{msg['player']}: {msg['message']}")

        elif msg["type"] == "ready_status":
            self.append_chat(f"{msg['player']} este gata!")

        elif msg["type"] == "init":
            print(f"[CLIENT {self.name}] INIT message received with data: {msg}")
            self.board.clear()
            self.game_active = True
            self.is_my_turn = msg["is_my_turn"]
            self.player_symbol = msg["player_symbol"]

            # Actualizează tabla din mesajul server-ului
            if "board" in msg and msg["board"]:
                self.board.update(msg["board"])

            self.draw_board()
            self.append_chat("Jocul începe!")

            turn_text = "Rândul tău!" if self.is_my_turn else f"Rândul lui {msg.get('current_turn_player_name', 'adversarul')}"
            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | {turn_text}")
            self.ready_btn.config(state='disabled')

            print(
                f"[CLIENT {self.name}] INIT processed. Game active: {self.game_active}, My turn: {self.is_my_turn}, My symbol: {self.player_symbol}")

        elif msg["type"] == "update":
            print(
                f"[CLIENT {self.name}] UPDATE received: x={msg['x']}, y={msg['y']}, player_symbol={msg['player_symbol']}, is_my_turn={msg['is_my_turn']}")

            # Actualizează tabla
            self.board[(msg["x"], msg["y"])] = msg["player_symbol"]
            self.is_my_turn = msg["is_my_turn"]

            print(f"[CLIENT {self.name}] Board updated. My turn now: {self.is_my_turn}")
            print(
                f"[CLIENT {self.name}] Current board state: {dict(list(self.board.items())[:5])}...")  # Arată primele 5 piese

            self.draw_board()
            turn_text = "Rândul tău!" if self.is_my_turn else f"Rândul lui {msg.get('turn', 'adversarul')}"
            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | {turn_text}")

        elif msg["type"] == "win":
            print(f"[CLIENT {self.name}] WIN received: winner={msg['winner']}")

            # Actualizează tabla cu ultima mutare
            if msg["x"] != -1 and msg["y"] != -1:  # -1,-1 înseamnă abandon
                self.board[(msg["x"], msg["y"])] = msg["player_symbol"]

            self.draw_board()
            winner = msg["winner"]
            self.append_chat(f"{winner} a câștigat!")
            self.game_active = False
            self.is_my_turn = False

            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | {winner} a câștigat!")
            messagebox.showinfo("Final", f"{winner} a câștigat!", parent=self.root)

            # Resetează pentru un joc nou
            self.ready_btn.config(state='normal', text="✅ Sunt gata")
            self.is_ready = False
            self.board.clear()
            self.draw_board()

        elif msg["type"] == "error":
            self.show_error(msg["message"])
            print(f"[CLIENT {self.name}] Error received: {msg['message']}")

    def draw_board(self):
        self.canvas.delete("all")

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            print(f"[CLIENT {self.name}] DEBUG: Canvas size invalid ({canvas_width}x{canvas_height}), skipping draw.")
            return

        current_cell_size = self.cell_size * self.zoom_level

        start_col = math.floor((-self.offset_x) / current_cell_size)
        end_col = math.ceil((canvas_width - self.offset_x) / current_cell_size)
        start_row = math.floor((-self.offset_y) / current_cell_size)
        end_row = math.ceil((canvas_height - self.offset_y) / current_cell_size)

        print(f"[CLIENT {self.name}] DEBUG: draw_board called. Board has {len(self.board)} pieces")
        print(
            f"[CLIENT {self.name}] DEBUG: current_cell_size: {current_cell_size}, offset_x: {self.offset_x}, offset_y: {self.offset_y}")
        print(f"[CLIENT {self.name}] DEBUG: Visible cols: {start_col}-{end_col}, rows: {start_row}-{end_row}")

        # Desenează grila
        for col in range(start_col - 1, end_col + 1):
            canvas_x = self.offset_x + col * current_cell_size
            self.canvas.create_line(canvas_x, 0, canvas_x, canvas_height, fill="#e0e0e0", width=1)
            if col % 5 == 0:
                self.canvas.create_text(canvas_x, 10, text=str(col), fill="gray", font=("Arial", 8))

        for row in range(start_row - 1, end_row + 1):
            canvas_y = self.offset_y + row * current_cell_size
            self.canvas.create_line(0, canvas_y, canvas_width, canvas_y, fill="#e0e0e0", width=1)
            if row % 5 == 0:
                self.canvas.create_text(10, canvas_y, text=str(row), fill="gray", font=("Arial", 8))

        # Desenează piesele
        pieces_drawn = 0
        for (x, y), player_symbol in self.board.items():
            px = self.offset_x + x * current_cell_size
            py = self.offset_y + y * current_cell_size

            if px + current_cell_size > 0 and px < canvas_width and \
                    py + current_cell_size > 0 and py < canvas_height:

                color = "#4285F4" if player_symbol == PLAYER_X else "#EA4335"
                outline = "#3367D6" if player_symbol == PLAYER_X else "#D33426"

                padding = 3 * self.zoom_level
                line_width = max(1, int(3 * self.zoom_level))

                if player_symbol == PLAYER_O:
                    self.canvas.create_oval(px + padding, py + padding,
                                            px + current_cell_size - padding, py + current_cell_size - padding,
                                            fill=color, outline=outline, width=max(1, int(2 * self.zoom_level)))
                    print(f"[CLIENT {self.name}] DEBUG: Drawn O at ({x},{y}) on canvas ({px},{py})")
                else:
                    self.canvas.create_line(px + padding, py + padding,
                                            px + current_cell_size - padding, py + current_cell_size - padding,
                                            fill=color, width=line_width)
                    self.canvas.create_line(px + current_cell_size - padding, py + padding,
                                            px + padding, py + current_cell_size - padding,
                                            fill=color, width=line_width)
                    print(f"[CLIENT {self.name}] DEBUG: Drawn X at ({x},{y}) on canvas ({px},{py})")
                pieces_drawn += 1

        print(f"[CLIENT {self.name}] DEBUG: Drew {pieces_drawn} pieces out of {len(self.board)} total")

    def on_canvas_resize(self, event):
        self.draw_board()

    def on_canvas_press(self, event):
        self.is_dragging = True
        self.has_dragged = False
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.mouse_press_x = event.x
        self.mouse_press_y = event.y

    def on_canvas_drag(self, event):
        if self.is_dragging:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            # Dacă mouse-ul s-a mișcat suficient, considerăm că e drag
            if abs(event.x - self.mouse_press_x) > self.drag_threshold or abs(
                    event.y - self.mouse_press_y) > self.drag_threshold:
                self.has_dragged = True

            self.offset_x += dx
            self.offset_y += dy
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.draw_board()

    def on_canvas_release(self, event):
        if self.is_dragging:
            # Dacă nu a fost drag, tratează ca click
            if not self.has_dragged:
                current_cell_size = self.cell_size * self.zoom_level
                x_logical = math.floor((event.x - self.offset_x) / current_cell_size)
                y_logical = math.floor((event.y - self.offset_y) / current_cell_size)
                print(f"[CLIENT {self.name}] Click detected at logical position ({x_logical}, {y_logical})")
                self.click_logic(x_logical, y_logical)

            self.is_dragging = False
            self.has_dragged = False

    def on_mouse_wheel(self, event):
        zoom_factor = 1.1
        if hasattr(event, 'delta'):
            if event.delta < 0:
                zoom_factor = 1 / 1.1
        elif event.num == 5:
            zoom_factor = 1 / 1.1
        elif event.num == 4:
            zoom_factor = 1.1

        old_zoom = self.zoom_level
        self.zoom_level = max(0.2, min(3.0, self.zoom_level * zoom_factor))

        mouse_x = event.x
        mouse_y = event.y

        logical_x_at_mouse = (mouse_x - self.offset_x) / old_zoom / self.cell_size
        logical_y_at_mouse = (mouse_y - self.offset_y) / old_zoom / self.cell_size

        self.offset_x = mouse_x - logical_x_at_mouse * self.zoom_level * self.cell_size
        self.offset_y = mouse_y - logical_y_at_mouse * self.zoom_level * self.cell_size

        self.draw_board()

    def click_logic(self, x_logical, y_logical):
        print(f"[CLIENT {self.name}] Click logic called:")
        print(f"  Position: ({x_logical},{y_logical})")
        print(f"  Game active: {self.game_active}")
        print(f"  Is ready: {self.is_ready}")
        print(f"  My turn: {self.is_my_turn}")
        print(f"  Player symbol: {self.player_symbol}")
        print(f"  Cell occupied: {(x_logical, y_logical) in self.board}")

        # Verificări în ordine
        if not self.game_active:
            self.update_info_bar("Jocul nu este activ încă!")
            self.append_chat("DEBUG: Jocul nu este activ!")
            return

        if not self.is_ready:
            self.update_info_bar("Nu ești gata încă!")
            self.append_chat("DEBUG: Nu ești gata!")
            return

        if self.player_symbol is None:
            self.update_info_bar("Simbolul jucătorului nu este atribuit încă.")
            self.append_chat("DEBUG: Simbol nedefinit!")
            return

        if not self.is_my_turn:
            self.update_info_bar("Nu este rândul tău!")
            self.append_chat("DEBUG: Nu este rândul tău!")
            return

        if (x_logical, y_logical) in self.board:
            self.update_info_bar("Celulă deja ocupată!")
            self.append_chat("DEBUG: Celulă ocupată!")
            return

        # Dacă ajungem aici, mutarea e validă
        print(f"[CLIENT {self.name}] Sending valid move to server")
        try:
            self.sock.sendall(pickle.dumps({
                "type": "move",
                "x": x_logical,
                "y": y_logical,
                "player_symbol": self.player_symbol
            }))

            # Nu schimba is_my_turn aici, serverul va trimite update
            self.update_info_bar(
                f"{self.name} | Camera: {self.room_id} | Jucător: {'X' if self.player_symbol == PLAYER_X else 'O'} | Așteaptă...")
            self.append_chat(f"Ai făcut mutarea la ({x_logical}, {y_logical})")
            print(f"[CLIENT {self.name}] Move sent successfully to server")

        except Exception as e:
            self.show_error(f"Eroare la trimiterea mutării: {e}")
            print(f"[CLIENT {self.name}] Error sending move: {e}")

    def send_ready(self):
        if self.is_ready:
            return

        self.is_ready = True
        try:
            self.sock.sendall(pickle.dumps({"type": "ready", "player_name": self.name}))
            self.ready_btn.config(state='disabled', text="✓ Gata")
            self.update_info_bar("Așteaptă ca adversarul să fie gata...")
            self.append_chat("Ai marcat că ești gata!")
            print(f"[CLIENT {self.name}] Sent ready message. is_ready = True.")
        except Exception as e:
            self.show_error(f"Eroare la trimiterea ready: {e}")

    def send_chat(self, event=None):
        text = self.entry.get().strip()
        if text:
            try:
                self.sock.sendall(pickle.dumps({"type": "chat", "message": text, "player_name": self.name}))
                self.entry.delete(0, tk.END)
            except Exception as e:
                self.show_error(f"Eroare la trimiterea mesajului: {e}")

    def append_chat(self, text):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, text + "\n")
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

    def show_info(self, text):
        messagebox.showinfo("Info", text, parent=self.root)

    def show_error(self, text):
        messagebox.showerror("Eroare", text, parent=self.root)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    GameClient().run()
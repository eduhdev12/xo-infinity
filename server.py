import socket
import threading
import pickle
import uuid
from collections import defaultdict

PLAYER_X = 1
PLAYER_O = 2


class GameServer:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")

        self.rooms = {}
        self.player_names_to_room = {}
        self.players_in_room_order = defaultdict(list)
        self.players_ready = defaultdict(set)

    def start(self):
        while True:
            conn, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        player_name = None
        room_id = None
        try:
            player_name = conn.recv(1024).decode("utf-8").strip()
            print(f"[SERVER] Player {player_name} connected from {addr}")

            choice_data = conn.recv(1024).decode("utf-8").strip()

            if choice_data == "CREATE":
                room_id = str(uuid.uuid4())[:8].upper()
                self.rooms[room_id] = {
                    'players': {},
                    'board': {},
                    'turn': None,
                    'game_started': False,
                    'player_symbols': {},
                    'game_over': False,
                    'winner': None
                }
                self.rooms[room_id]['players'][player_name] = conn
                self.player_names_to_room[player_name] = room_id
                self.players_in_room_order[room_id].append(player_name)
                self.rooms[room_id]['player_symbols'][player_name] = PLAYER_X
                print(f"[SERVER] Player {player_name} created room {room_id} and is {PLAYER_X}")
                self.send_message(conn, {"type": "room_created", "room_id": room_id, "player": PLAYER_X})

            elif choice_data.startswith("JOIN"):
                room_id = choice_data.split(" ")[1]
                if room_id not in self.rooms or len(self.rooms[room_id]['players']) >= 2:
                    self.send_message(conn, {"type": "error", "message": "Camera nu există sau este plină."})
                    conn.close()
                    return

                self.rooms[room_id]['players'][player_name] = conn
                self.player_names_to_room[player_name] = room_id
                self.players_in_room_order[room_id].append(player_name)
                self.rooms[room_id]['player_symbols'][player_name] = PLAYER_O
                print(f"[SERVER] Player {player_name} joined room {room_id} and is {PLAYER_O}")
                self.send_message(conn, {"type": "room_joined", "room_id": room_id, "player": PLAYER_O})

            else:
                self.send_message(conn, {"type": "error", "message": "Comandă invalidă."})
                conn.close()
                return

            self.broadcast_room_info(room_id)

            while True:
                data = conn.recv(4096)
                if not data:
                    break
                msg = pickle.loads(data)
                self.handle_message(player_name, room_id, msg)

        except Exception as e:
            print(f"[SERVER] Error handling client {player_name}: {e}")
        finally:
            if player_name:
                print(f"[SERVER] Player {player_name} disconnected.")
                self.remove_player_from_room(player_name, room_id, conn)
            else:
                conn.close()

    def init_board(self):
        return [[0 for _ in range(3)] for _ in range(3)]

    def send_message(self, conn, msg):
        try:
            conn.sendall(pickle.dumps(msg))
        except Exception as e:
            print(f"[SERVER] Error sending message: {e}")

    def broadcast_to_room(self, room_id, msg):
        if room_id not in self.rooms:
            return
        for name, client_conn in self.rooms[room_id]['players'].items():
            self.send_message(client_conn, msg)

    def broadcast_room_info(self, room_id):
        if room_id not in self.rooms:
            return

        players_info_list = []
        for name in self.players_in_room_order[room_id]:
            symbol = self.rooms[room_id]['player_symbols'].get(name, '?')
            is_ready = name in self.players_ready[room_id]
            players_info_list.append({"name": name, "symbol": symbol, "is_ready": is_ready})

        self.broadcast_to_room(room_id, {
            "type": "room_info",
            "players_info": players_info_list
        })

    def handle_message(self, player_name, room_id, msg):
        room = self.rooms.get(room_id)
        if not room:
            print(f"[SERVER] Room {room_id} not found for player {player_name}")
            return

        if msg["type"] == "chat":
            print(f"[SERVER] Chat from {msg.get('player_name', 'Unknown')} in {room_id}: {msg['message']}")
            self.broadcast_to_room(room_id, {
                "type": "chat",
                "player": msg.get("player_name", "Unknown"),
                "message": msg["message"]
            })

        elif msg["type"] == "ready":
            self.players_ready[room_id].add(player_name)
            print(f"[SERVER] Player {player_name} is ready in room {room_id}")
            self.broadcast_room_info(room_id)

            if len(self.players_ready[room_id]) == 2 and len(room['players']) == 2:
                self.start_game(room_id)

        elif msg["type"] == "move":
            self.handle_move(player_name, room_id, msg)

        elif msg["type"] == "restart_game":
            if room['game_over']:
                self.restart_game(room_id)

    def start_game(self, room_id):
        room = self.rooms[room_id]
        room['game_started'] = True
        room['game_over'] = False
        room['winner'] = None
        room['board'] = {}

        first_player = self.players_in_room_order[room_id][0]
        room['turn'] = first_player

        print(f"[SERVER] Game started in room {room_id}. Turn: {first_player}")

        for player_name in room['players']:
            is_my_turn = (player_name == first_player)
            self.send_message(room['players'][player_name], {
                "type": "init",
                "board": room['board'],
                "is_my_turn": is_my_turn,
                "player_symbol": room['player_symbols'][player_name],
                "current_turn_player_name": first_player
            })

    def handle_move(self, player_name, room_id, msg):
        room = self.rooms[room_id]

        if not room['game_started'] or room['game_over']:
            return

        if room['turn'] != player_name:
            self.send_message(room['players'][player_name], {
                "type": "error",
                "message": "Nu este rândul tău!"
            })
            return

        x, y = msg['x'], msg['y']

        if (x, y) in room['board']:
            self.send_message(room['players'][player_name], {
                "type": "error",
                "message": "Mutare invalidă!"
            })
            return

        player_symbol = room['player_symbols'][player_name]
        room['board'][(x, y)] = player_symbol

        print(f"[SERVER] Player {player_name} moved to ({x}, {y}) in room {room_id}")

        winner = self.check_winner_infinite(room['board'], x, y, player_symbol)

        if winner:
            room['game_over'] = True
            room['winner'] = winner

            winner_name = None
            for name, symbol in room['player_symbols'].items():
                if symbol == winner:
                    winner_name = name
                    break

            for other_player_name in room['players']:
                self.send_message(room['players'][other_player_name], {
                    "type": "win",
                    "x": x,
                    "y": y,
                    "player_symbol": player_symbol,
                    "winner": winner_name
                })
            print(f"[SERVER] Game over in room {room_id}. Winner: {winner_name}")
        else:
            current_index = self.players_in_room_order[room_id].index(player_name)
            next_index = (current_index + 1) % len(self.players_in_room_order[room_id])
            next_player = self.players_in_room_order[room_id][next_index]
            room['turn'] = next_player

            for other_player_name in room['players']:
                is_my_turn = (other_player_name == next_player)
                self.send_message(room['players'][other_player_name], {
                    "type": "update",
                    "x": x,
                    "y": y,
                    "player_symbol": player_symbol,
                    "is_my_turn": is_my_turn,
                    "turn": next_player
                })

    def check_winner_infinite(self, board, x, y, player_symbol):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for dx, dy in directions:
            count = 1

            i, j = x + dx, y + dy
            while (i, j) in board and board[(i, j)] == player_symbol:
                count += 1
                i, j = i + dx, j + dy

            i, j = x - dx, y - dy
            while (i, j) in board and board[(i, j)] == player_symbol:
                count += 1
                i, j = i - dx, j - dy

            if count >= 5:
                return player_symbol

        return None

    def check_winner(self, board):
        for row in board:
            if row[0] == row[1] == row[2] != 0:
                return row[0]

        for col in range(3):
            if board[0][col] == board[1][col] == board[2][col] != 0:
                return board[0][col]

        if board[0][0] == board[1][1] == board[2][2] != 0:
            return board[0][0]
        if board[0][2] == board[1][1] == board[2][0] != 0:
            return board[0][2]

        return None

    def is_board_full(self, board):
        for row in board:
            for cell in row:
                if cell == 0:
                    return False
        return True

    def restart_game(self, room_id):
        room = self.rooms[room_id]
        room['game_started'] = False
        room['game_over'] = False
        room['winner'] = None
        room['board'] = {}
        room['turn'] = None

        self.players_ready[room_id].clear()

        print(f"[SERVER] Game restarted in room {room_id}")

        self.broadcast_to_room(room_id, {
            "type": "game_restarted",
            "board": room['board']
        })

        self.broadcast_room_info(room_id)

    def remove_player_from_room(self, player_name, room_id, conn):
        try:
            conn.close()
        except:
            pass

        if not player_name or not room_id:
            return

        if room_id in self.rooms and player_name in self.rooms[room_id]['players']:
            del self.rooms[room_id]['players'][player_name]

        if player_name in self.player_names_to_room:
            del self.player_names_to_room[player_name]

        if room_id in self.players_in_room_order and player_name in self.players_in_room_order[room_id]:
            self.players_in_room_order[room_id].remove(player_name)

        if room_id in self.players_ready and player_name in self.players_ready[room_id]:
            self.players_ready[room_id].discard(player_name)

        if room_id in self.rooms and len(self.rooms[room_id]['players']) == 0:
            del self.rooms[room_id]
            if room_id in self.players_in_room_order:
                del self.players_in_room_order[room_id]
            if room_id in self.players_ready:
                del self.players_ready[room_id]
            print(f"[SERVER] Room {room_id} deleted (empty)")
        else:
            self.broadcast_to_room(room_id, {
                "type": "player_disconnected",
                "player": player_name
            })
            self.broadcast_room_info(room_id)

            if room_id in self.rooms and self.rooms[room_id]['game_started'] and not self.rooms[room_id]['game_over']:
                self.rooms[room_id]['game_over'] = True
                self.broadcast_to_room(room_id, {
                    "type": "game_interrupted",
                    "message": f"Jocul s-a întrerupt - {player_name} s-a deconectat"
                })


if __name__ == "__main__":
    server = GameServer()
    try:
        print("Starting Tic-Tac-Toe server...")
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        server.server_socket.close()
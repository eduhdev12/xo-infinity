✅ Prompt: Multiplayer Tic-Tac-Toe Game with Infinite Board (Python)

Objective:
Build a multiplayer Tic-Tac-Toe game with an infinite board using Python, with a secure centralized server to manage game logic and rooms.

⸻

🔧 Requirements:

1. Architecture
	•	Implement a centralized server that manages:
	•	Game rooms (creation, joining, player assignment)
	•	Game logic (turns, moves, win detection)
	•	Security (validate moves, prevent cheating)

2. Client Functionality
	•	Allow users to:
	•	Connect to the central server
	•	Create or join a room
	•	Wait for an opponent (max 2 players per room)
	•	Choose between X and O (unique per player)
	•	Players must not be able to choose the same symbol.
    •	Create and store leaderboard by name

3. Game Rules
	•	Implement an infinite board (no size limit)
	•	Use coordinate-based moves (e.g., (x, y))
	•	After each move:
	•	The server must check for a win condition
	•	Notify both players of the result (win/draw/continue)
	•	Only the player whose turn it is should be able to play.
	•	The other player must wait until their turn.

4. Security & Integrity
	•	All critical logic (e.g., move validation, win detection) must be done server-side.
	•	Prevent clients from:
	•	Making moves out of turn
	•	Sending invalid board positions
	•	Overwriting existing moves

5. Networking
	•	Use socket, asyncio, or WebSocket for real-time communication.
	•	Design the protocol for:
	•	Game events (e.g., join_room, make_move, player_ready, game_over)
	•	Server-client messaging in JSON or similar format

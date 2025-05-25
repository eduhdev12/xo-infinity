import socket
import json
import struct
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import threading
import queue

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Message:
    type: str
    data: Dict[str, Any]

class NetworkError(Exception):
    pass

class MessageProtocol:
    @staticmethod
    def pack_message(message: Message) -> bytes:
        """Pack a message into bytes for transmission"""
        message_bytes = json.dumps({
            "type": message.type,
            "data": message.data
        }).encode('utf-8')
        length = len(message_bytes)
        return struct.pack('!I', length) + message_bytes

    @staticmethod
    def unpack_message(data: bytes) -> Message:
        """Unpack bytes into a Message object"""
        try:
            message_dict = json.loads(data.decode('utf-8'))
            return Message(
                type=message_dict["type"],
                data=message_dict["data"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise NetworkError(f"Invalid message format: {str(e)}")

class TCPServer:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients: Dict[str, socket.socket] = {}
        self.message_handlers: Dict[str, callable] = {}
        self.running = False

    def start(self):
        """Start the TCP server"""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        logger.info(f"Server started on {self.host}:{self.port}")

        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                client_thread.start()
            except Exception as e:
                logger.error(f"Error accepting connection: {str(e)}")

    def stop(self):
        """Stop the TCP server"""
        self.running = False
        for client in self.clients.values():
            try:
                client.close()
            except:
                pass
        self.server_socket.close()

    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle a client connection"""
        client_id = f"{address[0]}:{address[1]}"
        self.clients[client_id] = client_socket
        
        try:
            while self.running:
                # Read message length (4 bytes)
                length_data = client_socket.recv(4)
                if not length_data:
                    break
                    
                length = struct.unpack('!I', length_data)[0]
                
                # Read message data
                data = b''
                while len(data) < length:
                    chunk = client_socket.recv(min(length - len(data), 4096))
                    if not chunk:
                        break
                    data += chunk
                
                if len(data) == length:
                    message = MessageProtocol.unpack_message(data)
                    if message.type in self.message_handlers:
                        self.message_handlers[message.type](client_id, message.data)
                    else:
                        logger.warning(f"Unknown message type: {message.type}")
                        
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {str(e)}")
        finally:
            del self.clients[client_id]
            client_socket.close()

    def send_message(self, client_id: str, message: Message):
        """Send a message to a specific client"""
        if client_id in self.clients:
            try:
                data = MessageProtocol.pack_message(message)
                self.clients[client_id].sendall(data)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {str(e)}")
                raise NetworkError(f"Failed to send message: {str(e)}")

class TCPClient:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.message_queue = queue.Queue()
        self.running = False
        self.message_handlers: Dict[str, callable] = {}

    def connect(self):
        """Connect to the server"""
        try:
            self.socket.connect((self.host, self.port))
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_messages)
            self.receive_thread.start()
            logger.info(f"Connected to server at {self.host}:{self.port}")
        except Exception as e:
            raise NetworkError(f"Failed to connect: {str(e)}")

    def disconnect(self):
        """Disconnect from the server"""
        self.running = False
        try:
            self.socket.close()
        except:
            pass

    def send_message(self, message: Message):
        """Send a message to the server"""
        try:
            data = MessageProtocol.pack_message(message)
            self.socket.sendall(data)
        except Exception as e:
            raise NetworkError(f"Failed to send message: {str(e)}")

    def _receive_messages(self):
        """Receive messages from the server"""
        while self.running:
            try:
                # Read message length (4 bytes)
                length_data = self.socket.recv(4)
                if not length_data:
                    break
                    
                length = struct.unpack('!I', length_data)[0]
                
                # Read message data
                data = b''
                while len(data) < length:
                    chunk = self.socket.recv(min(length - len(data), 4096))
                    if not chunk:
                        break
                    data += chunk
                
                if len(data) == length:
                    message = MessageProtocol.unpack_message(data)
                    if message.type in self.message_handlers:
                        self.message_handlers[message.type](message.data)
                    else:
                        logger.warning(f"Unknown message type: {message.type}")
                        
            except Exception as e:
                if self.running:
                    logger.error(f"Error receiving message: {str(e)}")
                break
        
        self.disconnect() 
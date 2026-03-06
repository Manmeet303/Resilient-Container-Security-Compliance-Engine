import json
from typing import List
from fastapi import WebSocket
from shared.utils.logger import get_logger

logger = get_logger("control_plane.ws_manager")

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message):
        payload = json.dumps(message, default=str)
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.active_connections.remove(d)

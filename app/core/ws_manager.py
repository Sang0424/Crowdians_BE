# app/core/ws_manager.py
import json
from typing import Dict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # 방(예: conversation_id) 단위로 WebSocket 연결들을 관리
        # room_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict):
        """특정 방에 있는 모든 클라이언트에게 JSON 메시지를 브로드캐스트"""
        if room_id in self.active_connections:
            message_str = json.dumps(message)
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_text(message_str)
                except Exception:
                    # 연결이 끊어진 경우 등에 대한 안전장치
                    pass

manager = ConnectionManager()

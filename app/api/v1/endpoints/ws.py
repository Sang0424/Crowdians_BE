# app/api/v1/endpoints/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.ws_manager import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: str):
    await manager.connect(websocket, channel_id)
    try:
        while True:
            # 클라이언트로부터 메시지를 수신 (개입 등은 HTTP API로 처리하더라도, 핑퐁용으로 둠)
            data = await websocket.receive_text()
            # 필요에 따라 수신한 메시지를 처리
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)

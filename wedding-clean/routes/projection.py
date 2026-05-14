from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import projection_manager

router = APIRouter()


@router.get("/state")
def get_projection_state_public():
    from routes.admin import _projection_state
    return _projection_state


@router.websocket("/ws")
async def projection_ws(websocket: WebSocket):
    await projection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        projection_manager.disconnect(websocket)

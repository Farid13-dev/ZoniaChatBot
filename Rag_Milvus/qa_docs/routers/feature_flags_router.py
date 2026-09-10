from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from qa_docs import save_context, context
import os

load_dotenv()

router_feature_flags = APIRouter()

connected_clients: list[WebSocket] = []

class ToggleRequest(BaseModel):
    key: str
    state: bool
    token: str

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

VALID_KEYS = ["subq_active", "tts_active"]

@router_feature_flags.get("/status")
async def get_flags(request: Request):
    return request.app.state.feature_flags

@router_feature_flags.post("/toggle")
async def toggle_flag(req: ToggleRequest, request: Request):
    if req.token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="No autorizado")

    if req.key not in VALID_KEYS:
        raise HTTPException(status_code=400, detail="Clave no válida")

    # 🔄 Actualizar tanto contexto como app state
    context[req.key] = req.state
    request.app.state.feature_flags[req.key] = req.state
    save_context()

    await notify_all_clients({
        "type": "feature_flags",  # usa un tipo consistente
        "data": request.app.state.feature_flags
    })

    return {req.key: req.state}

@router_feature_flags.websocket("/ws/feature_flags")
async def ws_feature_flags(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantener conexión viva
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

async def notify_all_clients(message: dict):
    living = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
            living.append(ws)
        except:
            pass
    connected_clients[:] = living

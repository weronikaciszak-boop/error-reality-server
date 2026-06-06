from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import datetime


game_state = {
    "power": False,
    "unlocked_modules": [],
    "restored_modules": [],
    "progress": 0,
    "core_status": "CORRUPTED"
}

def calculate_progress():

    progress = 0

    if game_state["power"]:
        progress += 4

    progress += len(game_state["unlocked_modules"]) * 12

    progress += len(game_state["restored_modules"]) * 12

    return min(progress, 100)
    
app = FastAPI()

# Zezwalamy frontendowi na komunikację z serwerem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definicja żądania weryfikacji hasła
class PuzzleCheck(BaseModel):
    module: str
    answer: str

# Bezpieczna baza haseł na serwerze
SECRET_ANSWERS = {
    "food": "arch",
    "living": "b",
    "memory": "cdba",
    "sanitation": "37767"
}

# Lista przechowująca tymczasowe logi systemowe
system_events = []

# Lista aktywnych połączeń WebSocket (telefony graczy)
active_connections: List[WebSocket] = []

@app.get("/")
def read_root():
    return {"status": "ERROR REALITY OS SERVER ACTIVE"}

# Endpoint, którego szukał Twój frontend (błąd 404 zniknie)
@app.get("/events")
def get_events():
    return {"events": system_events}

# Weryfikacja haseł
@app.post("/verify-puzzle")
async def verify_puzzle(payload: PuzzleCheck):
    module_name = payload.module
    user_answer = payload.answer.strip().lower()
    
    if module_name not in SECRET_ANSWERS:
        raise HTTPException(status_code=400, detail="Unknown module")
        
    if user_answer == SECRET_ANSWERS[module_name]:
     
        if module_name not in game_state["restored_modules"]:
        game_state["restored_modules"].append(module_name)
    
        game_state["progress"] = calculate_progress()

# Tworzymy log o sukcesie
        event_data = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "type": f"MODULE_{module_name.upper()}_RESTORED",
            "data": {"status": "SUCCESS"}
        }


        
        system_events.append(event_data)
        
        # Rozsyłamy info przez WebSocket do wszystkich połączonych urządzeń
        await broadcast_message(event_data)
        
        return {"status": "SUCCESS", "message": "Module restored"}
    else:
        raise HTTPException(status_code=401, detail="Invalid authorization code")

# Manager WebSocketów (błąd CONNECTION_REFUSED zniknie)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Utrzymujemy połączenie otwarte i nasłuchujemy (np. ping-pong)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_message(message: dict):
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            # Jeśli połączenie padło, zignoruj (zostanie usunięte przy rozłączeniu)
            pass

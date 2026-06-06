from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import datetime

app = FastAPI()

# =========================

# CORS

# =========================

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)

# =========================

# GAME STATE

# =========================

game_state = {
"power": False,
"unlocked_modules": [],
"restored_modules": [],
"progress": 0,
"core_status": "CORRUPTED"
}

system_events = []

active_connections: List[WebSocket] = []

# =========================

# MODELS

# =========================

class PuzzleCheck(BaseModel):
module: str
answer: str

# =========================

# ANSWERS

# =========================

SECRET_ANSWERS = {
"food": "arch",
"living": "b",
"memory": "cdba",
"sanitation": "37767"
}

# =========================

# HELPERS

# =========================

def calculate_progress():

```
progress = 0

if game_state["power"]:
    progress += 4

progress += len(game_state["unlocked_modules"]) * 12

progress += len(game_state["restored_modules"]) * 12

return min(progress, 100)
```

async def broadcast_state():

```
payload = {
    "type": "STATE_UPDATE",
    "events": system_events,
    "game_state": game_state
}

disconnected = []

for connection in active_connections:
    try:
        await connection.send_json(payload)
    except Exception:
        disconnected.append(connection)

for connection in disconnected:
    if connection in active_connections:
        active_connections.remove(connection)
```

# =========================

# BASIC ROUTES

# =========================

@app.get("/")
def read_root():
return {
"status": "ERROR REALITY OS SERVER ACTIVE"
}

@app.get("/events")
def get_events():
return {
"events": system_events,
"game_state": game_state
}

# =========================

# POWER

# =========================

@app.post("/power-on")
async def power_on():

```
game_state["power"] = True
game_state["progress"] = calculate_progress()

system_events.append({
    "timestamp": datetime.datetime.utcnow().isoformat(),
    "type": "POWER_ON",
    "data": {}
})

await broadcast_state()

return {"status": "OK"}
```

# =========================

# MODULE UNLOCK (NFC)

# =========================

@app.post("/unlock/{module}")
async def unlock_module(module: str):

```
if module not in [
    "food",
    "living",
    "memory",
    "sanitation"
]:
    raise HTTPException(
        status_code=400,
        detail="Unknown module"
    )

if module not in game_state["unlocked_modules"]:
    game_state["unlocked_modules"].append(module)

game_state["progress"] = calculate_progress()

system_events.append({
    "timestamp": datetime.datetime.utcnow().isoformat(),
    "type": "MODULE_UNLOCKED",
    "data": module
})

await broadcast_state()

return {"status": "OK"}
```

# =========================

# PUZZLES

# =========================

@app.post("/verify-puzzle")
async def verify_puzzle(payload: PuzzleCheck):

```
module_name = payload.module
user_answer = payload.answer.strip().lower()

if module_name not in SECRET_ANSWERS:
    raise HTTPException(
        status_code=400,
        detail="Unknown module"
    )

if user_answer != SECRET_ANSWERS[module_name]:
    raise HTTPException(
        status_code=401,
        detail="Invalid authorization code"
    )

if module_name not in game_state["restored_modules"]:
    game_state["restored_modules"].append(module_name)

game_state["progress"] = calculate_progress()

event_data = {
    "timestamp": datetime.datetime.utcnow().isoformat(),
    "type": f"MODULE_{module_name.upper()}_RESTORED",
    "data": {
        "status": "SUCCESS"
    }
}

system_events.append(event_data)

await broadcast_state()

return {
    "status": "SUCCESS",
    "message": "Module restored",
    "progress": game_state["progress"]
}
```

# =========================

# RESET

# =========================

@app.post("/reset")
async def reset_game():

```
game_state["power"] = False
game_state["unlocked_modules"] = []
game_state["restored_modules"] = []
game_state["progress"] = 0
game_state["core_status"] = "CORRUPTED"

system_events.clear()

await broadcast_state()

return {
    "status": "RESET_COMPLETE"
}
```

# =========================

# WEBSOCKET

# =========================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

```
await websocket.accept()

active_connections.append(websocket)

await websocket.send_json({
    "type": "STATE_UPDATE",
    "events": system_events,
    "game_state": game_state
})

try:
    while True:
        await websocket.receive_text()

except WebSocketDisconnect:
    if websocket in active_connections:
        active_connections.remove(websocket)
```

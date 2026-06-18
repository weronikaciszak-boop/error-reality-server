from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import datetime
import requests
import asyncio

app = FastAPI()

# Link z ngroka (pamiętaj o aktualizacji, jeśli zrestartujesz ngroka na komputerze!)
HA_URL = "https://aged-nutcase-nearby.ngrok-free.dev"

HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhMTU4OWM0ODFiY2Y0NmE0YTIyNmJjYmZhNDBhMzYyOSIsImlhdCI6MTc4MTEyMzY2MywiZXhwIjoyMDk2NDgzNjYzfQ.VQcvW23zRZ4OQSJbelXmQyDJEhaqCmkUd2DDVfoQcMk"

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
    "start_triggered": False,
    "unlocked_modules": [],
    "restored_modules": [],
    "progress": 0,
    "bad_floppy": False,
    "duck_bad": False,
    "duck_good": False,
    "core_status": "CORRUPTED"
}

system_events = []
active_connections: List[WebSocket] = []
active_players: List[WebSocket] = [] # Bezpieczna lista na połączenia graczy

SECRET_ANSWERS = {
    "food": "arch",
    "living": "b",
    "memory": "cdba",
    "sanitation": "37767"
}

# =========================
# MODELS
# =========================

class PuzzleCheck(BaseModel):
    module: str
    answer: str

# =========================
# HELPERS
# =========================

def calculate_progress():
    progress = 0
    if game_state["power"]:
        progress += 4
    progress += len(game_state["unlocked_modules"]) * 12
    progress += len(game_state["restored_modules"]) * 12
    return min(progress, 100)


async def broadcast_state():
    payload = {
        "type": "STATE_UPDATE",
        "events": system_events,
        "game_state": game_state
    }
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(payload)
        except:
            disconnected.append(connection)
    
    for connection in disconnected:
        if connection in active_connections:
            active_connections.remove(connection)
        if connection in active_players:
            active_players.remove(connection)

# =========================
# FUNCTION TO RUN WEBHOOKS IN HOME ASSISTANT
# =========================

async def run_scene(scene_name: str):
    try:
        webhook_mapping = {
            "error_start": "odpal_error_start",
            "error_end": "odpal_error_end",
            "error_sprzatanie": "odpal_error_sprzatanie"
        }
        
        actual_webhook = webhook_mapping.get(scene_name, scene_name)
        webhook_url = f"{HA_URL}/api/webhook/{actual_webhook}"
        
        print(f"Wysyłam żądanie POST na webhook: {webhook_url}")
        
        # NAGŁÓWKI OSZUKUJĄCE ZABEZPIECZENIA HA (Udajemy ruch lokalny)
        headers = {
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1"
        }
        
        loop = asyncio.get_event_loop()
        # Dodajemy 'headers=headers' do metody post:
        await loop.run_in_executor(None, lambda: requests.post(
            webhook_url,
            headers=headers,
            timeout=5
        ))
        print(f"Webhook {actual_webhook} wysłany pomyślnie do HA!")
        return {"status": "ok", "webhook_sent": actual_webhook}
    except Exception as e:
        print(f"Błąd wywołania webhooka {scene_name}: {e}")
        return {"status": "error", "message": str(e)}

# =========================
# OPÓŹNIONY FINAŁ (Balkon + 1 minuta)
# =========================

async def delayed_final_cleanup():
    await asyncio.sleep(60)
    game_state["core_status"] = "BOOTING COMPLETE"
    await broadcast_state()
    await run_scene("error_sprzatanie")
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.post(
            f"{HA_URL}/api/services/media_player/play_media",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "entity_id": "media_player.spotify_twoj_profil",
                "media_content_id": "spotify:playlist:IDENTYFIKATOR_TWOJEJ_PLAYLISTY",
                "media_content_type": "playlist"
            },
            timeout=5
        ))
    except Exception as e:
        print(f"Błąd uruchamiania Spotify: {e}")

# =========================
# ROUTES
# =========================

@app.get("/")
def read_root():
    return {"status": "ERROR REALITY OS SERVER ACTIVE"}


@app.get("/events")
def get_events():
    return {
        "events": system_events,
        "game_state": game_state
    }


@app.post("/verify-puzzle")
async def verify_puzzle(payload: PuzzleCheck):
    module_name = payload.module
    user_answer = payload.answer.strip().lower()

    if module_name not in SECRET_ANSWERS:
        raise HTTPException(status_code=400, detail="Unknown module")

    if user_answer != SECRET_ANSWERS[module_name]:
        raise HTTPException(status_code=401, detail="Invalid code")

    if module_name not in game_state["restored_modules"]:
        game_state["restored_modules"].append(module_name)

    game_state["progress"] = calculate_progress()

    event_data = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "type": f"MODULE_{module_name.upper()}_RESTORED",
        "data": module_name
    }
    system_events.append(event_data)
    await broadcast_state()

    return {
        "status": "SUCCESS",
        "progress": game_state["progress"]
    }


@app.post("/power-on")
async def power_on():

    if game_state["power"]:
        return {"status": "ALREADY_ON"}

    game_state["power"] = True
    game_state["progress"] = calculate_progress()

    system_events.append({
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "type": "POWER_ON",
        "data": {}
    })

    await broadcast_state()

    return {"status": "OK"}


@app.post("/unlock/{module}")
async def unlock_module(module: str):
    if module == "bad_floppy":
        if not game_state["bad_floppy"]:
            game_state["bad_floppy"] = True
            system_events.append({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "type": "BAD_FLOPPY_DETECTED",
                "data": {}
            })
        await broadcast_state()
        return {"status": "OK"}

    if module == "duck_bad":
        if not game_state["duck_bad"]:
            game_state["duck_bad"] = True
            system_events.append({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "type": "BAD_CORE_INSERTED",
                "data": {}
            })
        await broadcast_state()
        return {"status": "OK"}

    if module == "duck_good":
        if not game_state["duck_good"]:
            game_state["duck_good"] = True
            game_state["core_status"] = "EVACUATE TO BALCONY"
            system_events.append({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "type": "REALITY_REBOOTED",
                "data": {}
            })
        await broadcast_state()
        await run_scene("error_end")
        asyncio.create_task(delayed_final_cleanup())
        return {"status": "OK"}

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


@app.post("/reset")
async def reset_game_post():
    return await execute_reset()

@app.get("/lock-status")
async def lock_status():

    return {
        "unlock": (
    game_state["progress"] >= 100
    and not game_state["duck_good"]
),
        "progress": game_state["progress"],
        "modules": game_state["unlocked_modules"],
        "restored": game_state["restored_modules"]
    }
@app.get("/reset")
async def reset_game_get():
    return await execute_reset()


async def execute_reset():
    game_state["power"] = False
    game_state["start_triggered"] = False
    game_state["unlocked_modules"] = []
    game_state["restored_modules"] = []
    game_state["progress"] = 0
    game_state["bad_floppy"] = False
    game_state["duck_bad"] = False
    game_state["duck_good"] = False
    game_state["core_status"] = "CORRUPTED"
    system_events.clear()
    await broadcast_state()
    return {"status": "RESET_OK"}


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/scene/{scene_name}")
async def run_scene_endpoint(scene_name: str):
    return await run_scene(scene_name)


# =========================
# WEBSOCKET (W pełni bezpieczny dla Rendera)
# =========================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    client_type = websocket.query_params.get("client", "unknown")

    if client_type == "player" and not game_state["start_triggered"]:

        print("ERROR START")

        game_state["start_triggered"] = True

        system_events.append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "type": "ERROR_START",
            "data": {}
        })

        await run_scene("error_start")

    active_connections.append(websocket)

    if client_type == "player":
        active_players.append(websocket)

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

        if websocket in active_players:
            active_players.remove(websocket)

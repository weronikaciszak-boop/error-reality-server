from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import datetime
import requests
import asyncio  # Dodane do obsługi odliczania minuty

app = FastAPI()

# Twój aktualny link z ngroka (pamiętaj, aby go zmienić, jeśli zrestartujesz ngroka!)
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

# =========================
# FUNCTION TO RUN WEBHOOKS IN HOME ASSISTANT
# =========================

async def run_scene(scene_name: str):
    try:
        # Mapujemy nazwy z kodu na Twoje dokładne nazwy webhooków w HA
        webhook_mapping = {
            "error_start": "odpal_error_start",
            "error_end": "odpal_error_end",         # <--- upewnij się, że tak nazwałaś webhook w HA
            "error_sprzatanie": "odpal_error_sprzatanie" # <--- upewnij się, że tak nazwałaś webhook w HA
        }
        
        actual_webhook = webhook_mapping.get(scene_name, scene_name)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.post(
            f"{HA_URL}/api/webhook/{actual_webhook}", # Strzelamy prosto w webhook ngroka
            timeout=5
        ))
        print(f"Webhook {actual_webhook} wysłany pomyślnie!")
        return {"status": "ok"}
    except Exception as e:
        print(f"Błąd wywołania webhooka {scene_name}: {e}")
        return {"status": "error", "message": str(e)}

# =========================
# OPÓŹNIONY FINAŁ (Balkon + 1 minuta)
# =========================

async def delayed_final_cleanup():
    # Czekamy dokładnie 60 sekund w tle
    await asyncio.sleep(60)
    
    # Zmiana statusu na ekranie TV
    game_state["core_status"] = "BOOTING COMPLETE"
    await broadcast_state()
    
    # Odpalenie sceny sprzątania w Home Assistant
    await run_scene("error_sprzatanie")
    
    # Odpalenie Spotify przez Home Assistant
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.post(
            f"{HA_URL}/api/services/media_player/play_media",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "entity_id": "media_player.spotify_twoj_profil",  # <-- Podmień na swoją encję Spotify z HA!
                "media_content_id": "spotify:playlist:IDENTYFIKATOR_TWOJEJ_PLAYLISTY",  # <-- Podmień na link do playlisty!
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

    # POPRAWNA KACZKA - EWAKUACJA + ODLICZANIE MINUTY
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
        
        # 1. Odpalenie sceny ewakuacji (error_end)
        await run_scene("error_end")
        
        # 2. Start odliczania minuty w tle (balkon)
        asyncio.create_task(delayed_final_cleanup())
        return {"status": "OK"}

    # Standardowe moduły nfc
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
async def reset_game():
    game_state["power"] = False
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


@app.get("/scene/{scene_name}")
async def run_scene_endpoint(scene_name: str):
    # Zachowujemy stary endpoint, żeby niczego nie zepsuć w innych plikach
    return await run_scene(scene_name)


# =========================
# ZMODYFIKOWANY WEBSOCKET (Start gry tylko przez index.html)
# =========================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Sprawdzamy parametry połączenia (kto się łączy)
    client_type = websocket.query_params.get("client", "unknown")

    # Scena startowa odpala się TYLKO gdy łączy się PIERWSZY gracz (index.html),
    # a nie telewizor (TV.html) i gdy gra jeszcze nie ruszyła
    if client_type == "player" and len([c for c in active_connections if getattr(c, 'is_player', False)]) == 0 and not game_state["power"]:
        print("Pierwszy GRACZ połączony przez index.html! Odpalam scenę startową...")
        
        game_state["power"] = True
        game_state["progress"] = calculate_progress()
        system_events.append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "type": "POWER_ON",
            "data": {}
        })
        # Odpalenie sceny startowej w HA (error_start)
        await run_scene("odpal_error_start_naz")

    # Oznaczamy połączenie, żeby serwer pamiętał, kto jest kim
    if client_type == "player":
        websocket.is_player = True
    else:
        websocket.is_player = False

    active_connections.append(websocket)

    # Wysyłamy aktualny stan gry do nowo połączonego ekranu
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

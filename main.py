from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Zezwalamy frontendowi na komunikację z serwerem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definicja tego, jak ma wyglądać zapytanie z telefonu
class PuzzleCheck(BaseModel):
    module: str
    answer: str

# Baza poprawnych haseł - bezpieczna, ukryta na serwerze!
SECRET_ANSWERS = {
    "food": "arch",
    "living": "b",
    "memory": "cdba",
    "sanitation": "37767"
}

@app.get("/")
def read_root():
    return {"status": "ERROR REALITY OS SERVER ACTIVE"}

@app.post("/verify-puzzle")
def verify_puzzle(payload: PuzzleCheck):
    module_name = payload.module
    user_answer = payload.answer.strip().lower()
    
    if module_name not in SECRET_ANSWERS:
        raise HTTPException(status_code=400, detail="Unknown module")
        
    if user_answer == SECRET_ANSWERS[module_name]:
        # === MIEJSCE NA TWOJE SMART HOME ===
        # Tutaj w przyszłości dopiszemy kod, który np. odpala webhooka w Home Assistant!
        # trigger_smart_home_action(module_name)
        
        return {"status": "SUCCESS", "message": "Module restored"}
    else:
        raise HTTPException(status_code=401, detail="Invalid authorization code")

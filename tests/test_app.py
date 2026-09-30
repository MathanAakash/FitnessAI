import os
os.environ["GEMINI_API_KEY"] = ""
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
init_db()

client = TestClient(app)

def test_home():
    r=client.get("/")
    assert r.status_code==200
    assert "FitBuddy" in r.text

def test_health():
    r=client.get("/api/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_generate_and_feedback():
    payload={"username":"Test User","user_id":"TEST001","age":25,"weight":70,"goal":"general wellness","intensity":"medium"}
    r=client.post("/api/generate-workout",json=payload)
    assert r.status_code==200
    assert "Day 1" in r.json()["workout_plan"]
    r=client.post("/api/submit-feedback",json={"user_id":"TEST001","feedback":"Add more cardio and an extra rest day."})
    assert r.status_code==200
    assert "updated_plan" in r.json()

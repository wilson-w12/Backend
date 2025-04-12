
import pytest
import sys
import os
import json
from pymongo import MongoClient
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app

# ---------- SETUP ----------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    mongo_uri = "mongodb+srv://wilsonw12:14Ts5mW4bs7H6dWO@com668class.nre7q.mongodb.net/?retryWrites=true&w=majority&appName=Com668CLASS"
    client = MongoClient(mongo_uri)
    db = client["COM668Coursework"]
    assert db.command("ping")["ok"] == 1, "Failed to connect to MongoDB Atlas"
    yield
    client.close()

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client

@pytest.fixture
def auth_header(client):
    login_data = {
        "email": "admin@admin.com",
        "password": "test"
    }
    response = client.post("/api/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.data}"
    token = response.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_classes_per_subject(client, auth_header):
    response = client.get('/api/teacher/classes/subjects/total', headers=auth_header)
    assert response.status_code == 200
    assert 'subjects' in response.get_json()

def test_assignments_exams_due_today(client, auth_header):
    response = client.get('/api/teacher/assignments-exams-due-today', headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    assert 'assignments_due_today' in data
    assert 'exams_due_today' in data

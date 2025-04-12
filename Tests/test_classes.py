
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

def test_add_class(client, auth_header):
    class_data = {
        "_id": "C00Test",
        "subject": "Science",
        "year": 10,
        "set": "Z",
        "teacher_ids": [],
        "student_ids": []
    }
    response = client.post(
        "/api/classes",
        data=json.dumps(class_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code in [200, 201]  
    assert response.json["class_id"] == "C00Test"

def test_get_classes_filters(client, auth_header):
    response = client.get('/api/classes/classes-filters', headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    assert 'subjects' in data

def test_get_all_classes(client, auth_header):
    response = client.get('/api/classes', headers=auth_header)
    assert response.status_code == 200
    assert 'classes' in response.get_json()

def test_get_teacher_classes(client, auth_header):
    response = client.get('/api/teacher/classes', headers=auth_header)
    assert response.status_code == 200
    assert 'classes' in response.get_json()

def test_get_classes_total(client, auth_header):
    response = client.get('/api/teacher/classes/total', headers=auth_header)
    assert response.status_code == 200
    assert 'total_classes' in response.get_json()

def test_get_class(client, auth_header):
    response = client.get("/api/classes/C00Test", headers=auth_header)
    assert response.status_code == 200
    assert response.json["class"]["_id"] == "C00Test" 

def test_edit_class_teacher(client, auth_header):
    update_data = {
        "teacher_ids": ["603ddf3f9a1d8c0015c9e0c3"]
    }
    response = client.put(
        "/api/classes/C00Test",
        data=json.dumps(update_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == 200

def test_delete_class(client, auth_header):
    response = client.delete("/api/classes/C00Test", headers=auth_header)
    assert response.status_code == 200
    assert response.json["message"] == "Class deleted successfully"

import pytest
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app
from pymongo import MongoClient
from bson import ObjectId

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
    token = response.json["token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def created_student(client, auth_header):
    student_data = {
        "first_name": "Testy",
        "last_name": "McTestface",
        "gender": "Other",
        "year": 9,
        "set": "B",
        "target_grades": {"math": "A"},
        "teachers": {"math": "603ddf3f9a1d8c0015c9e0c3"},
        "class_ids": []
    }

    response = client.post(
        "/api/students",
        data=json.dumps(student_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )

    assert response.status_code == 201
    return response.json["student_id"]

# Add student
def test_add_student(client, auth_header):
    student_data = {
        "first_name": "TestAdd",
        "last_name": "Student",
        "gender": "Male",
        "year": 10,
        "set": "A",
        "target_grades": {"science": "B"},
        "teachers": {"science": "603ddf3f9a1d8c0015c9e0c3"},
        "class_ids": []
    }

    response = client.post(
        "/api/students",
        data=json.dumps(student_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )

    assert response.status_code == 201
    assert "student_id" in response.json

# Get student
def test_get_student(client, auth_header, created_student):
    student_id = created_student
    get_resp = client.get(f"/api/students/{student_id}", headers=auth_header)
    assert get_resp.status_code == 200
    assert get_resp.json["first_name"] == "Testy"

# Edit student 
def test_edit_student(client, auth_header, created_student):
    student_id = created_student
    edit_resp = client.put(
        f"/api/students/{student_id}",
        data=json.dumps({"first_name": "UpdatedTesty"}),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert edit_resp.status_code == 200

# Delete student
def test_delete_student(client, auth_header, created_student):
    student_id = created_student
    del_resp = client.delete(f"/api/students/{student_id}", headers=auth_header)
    assert del_resp.status_code == 200
    assert del_resp.json["message"] == "Student deleted successfully"



def test_add_student_missing_fields(client, auth_header):
    response = client.post('/api/students', json={"first_name": "Test"}, headers=auth_header)
    assert response.status_code == 400
    assert "Missing required fields" in response.get_data(as_text=True)

def test_edit_nonexistent_student(client, auth_header):
    response = client.put('/api/students/605c3c0f4a8e4b26f0b3e9f0', json={"first_name": "Updated"}, headers=auth_header)
    assert response.status_code in [404, 200]  

def test_get_students_with_filters(client, auth_header):
    response = client.get('/api/students?page=1&page_size=5&year=2023', headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    assert "students" in data

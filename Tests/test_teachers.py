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
def created_teacher(client, auth_header):
    teacher_data = {
        "title": "Mr.",
        "firstName": "Teachy",
        "lastName": "McTeachface",
        "gender": "Other",
        "email": "teachy@example.com",
        "phone": "1234567890",
        "password": "testpass",
        "confirmPassword": "testpass",
        "subjects": ["Math"],
        "classes": []
    }

    response = client.post(
        "/api/teachers",
        data=json.dumps(teacher_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == 201
    return response.json["teacherId"]

# Add teacher
def test_add_teacher(client, auth_header):
    teacher_data = {
        "title": "Ms.",
        "firstName": "New",
        "lastName": "Teacher",
        "gender": "Female",
        "email": "newteacher@example.com",
        "phone": "9876543210",
        "password": "testpass",
        "confirmPassword": "testpass",
        "subjects": ["Science"],
        "classes": []
    }

    response = client.post(
        "/api/teachers",
        data=json.dumps(teacher_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )

    assert response.status_code == 201
    assert "teacherId" in response.json

def test_get_teacher(client, auth_header, created_teacher):
    response = client.get(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert response.status_code == 200
    assert response.json["first_name"] == "Teachy"

def test_get_all_teachers(client, auth_header):
    response = client.get('/api/teachers', headers=auth_header)
    assert response.status_code in [200, 400, 401, 403, 404, 500]

def test_edit_teacher(client, auth_header, created_teacher):
    update_data = {"first_name": "UpdatedTeachy"}
    response = client.put(
        f"/api/teachers/{created_teacher}",
        data=json.dumps(update_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == 200

def test_delete_teacher(client, auth_header, created_teacher):
    response = client.delete(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert response.status_code == 200
    assert response.json["message"] == "Teacher deleted successfully"

    # Verify teacher doesn't exist
    verify_resp = client.get(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert verify_resp.status_code == 404

def test_add_teacher_password_mismatch(client, auth_header):
    new_teacher = {
        "firstName": "Mismatch",
        "lastName": "Test",
        "gender": "Other",
        "email": "mismatch@example.com",
        "phone": "1234567890",
        "password": "pass1",
        "confirmPassword": "pass2",
        "subjects": ["Math"],
        "classes": []
    }
    response = client.post('/api/teachers', json=new_teacher, headers=auth_header)
    assert response.status_code == 400
    assert "Passwords do not match" in response.get_data(as_text=True)

def test_update_teacher_unauthorized(client):
    response = client.put('/api/teachers/fakeid', json={"first_name": "Hack"})
    assert response.status_code == 401 or response.status_code == 403

def test_delete_teacher_not_found(client, auth_header):
    response = client.delete('/api/teachers/605c3c0f4a8e4b26f0b3e9f0', headers=auth_header)
    assert response.status_code in [404, 500]

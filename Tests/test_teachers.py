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

# Get teacher
def test_get_teacher(client, auth_header, created_teacher):
    response = client.get(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert response.status_code == 200
    assert response.json["first_name"] == "Teachy"

# Edit teacher
def test_edit_teacher(client, auth_header, created_teacher):
    update_data = {"first_name": "UpdatedTeachy"}
    response = client.put(
        f"/api/teachers/{created_teacher}",
        data=json.dumps(update_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == 200

# Delete teacher
def test_delete_teacher(client, auth_header, created_teacher):
    response = client.delete(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert response.status_code == 200
    assert response.json["message"] == "Teacher deleted successfully"

    # Verify teacher doesn't exist
    verify_resp = client.get(f"/api/teachers/{created_teacher}", headers=auth_header)
    assert verify_resp.status_code == 404
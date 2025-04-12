import pytest
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app
from pymongo import MongoClient

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
    token = response.json["token"]
    return {"Authorization": f"Bearer {token}"}

# ---------- CLASSES ----------

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

# ---------- ASSIGNMENTS ----------

def test_add_and_delete_assignment(client, auth_header):
    assignment_data = {
        "title": "Test Assignment",
        "topics": ["Photosynthesis"],
        "due_date": "2025-04-15",
        "total_marks": 100,
        "A*_grade": 90,
        "A_grade": 80,
        "B_grade": 70,
        "C_grade": 60,
        "F_grade": 0,
        "results": [],  
        "class_id": "C00Test"
    }

    response = client.post(
        "/api/classes/C00Test/assignments",
        data=json.dumps(assignment_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )

    assert response.status_code == 201, f"Failed to create assignment: {response.data}"
    assignment_id = response.json["assignment_id"]

    # Cleanup
    delete_resp = client.delete(
        f"/api/classes/C00Test/assignments/{assignment_id}",
        headers=auth_header
    )
    assert delete_resp.status_code == 200, f"Failed to delete assignment: {delete_resp.data}"
    assert delete_resp.json["message"] == "Assignment deleted successfully"

# ---------- EXAMS ----------

def test_add_and_delete_exam(client, auth_header):
    exam_data = {
        "title": "Test Exam",
        "year": 8,
        "subject": "Maths",
        "due_date": "2025-04-20",
        "total_marks": 100,
        "A*_grade": 90,
        "A_grade": 80,
        "B_grade": 70,
        "C_grade": 60,
        "F_grade": 0,
        "results": []  
    }
    response = client.post(
        "/api/exams",
        data=json.dumps(exam_data),
        headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == 201
    exam_id = response.json["exam_id"]

    # Cleanup
    delete_resp = client.delete(f"/api/exams/{exam_id}", headers=auth_header)
    assert delete_resp.status_code == 200
    assert delete_resp.json["message"] == "Exam deleted successfully"

# ---------- CLEANUP ----------

def test_delete_class(client, auth_header):
    response = client.delete("/api/classes/C00Test", headers=auth_header)
    assert response.status_code == 200
    assert response.json["message"] == "Class deleted successfully"


def test_create_assignment_missing_fields(client, auth_header):
    response = client.post(
        '/api/classes/invalid_class_id/assignments',
        json={"title": "Incomplete Assignment"},
        headers=auth_header
    )
    assert response.status_code == 400
    assert "is required" in response.get_data(as_text=True)

def test_create_exam_invalid_data(client, auth_header):
    response = client.post(
        '/api/exams',
        json={"title": "Bad Exam"},
        headers=auth_header
    )
    assert response.status_code == 400
    assert "is required" in response.get_data(as_text=True)

def test_get_assignments_for_invalid_class(client, auth_header):
    response = client.get('/api/classes/invalid_class_id/assignments', headers=auth_header)
    assert response.status_code == 404

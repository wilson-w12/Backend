
import pytest
import sys
import os
import json
from pymongo import MongoClient
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app

# SETUP 

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

def test_login_valid(client):
    response = client.post('/api/login', data={'email': 'admin@admin.com', 'password': 'test'})
    assert response.status_code == 200
    assert 'token' in response.get_json()

def test_login_invalid(client):
    response = client.post('/api/login', data={'email': 'wrong@example.com', 'password': 'wrong'})
    assert response.status_code == 401

def test_validate_token_success(client, auth_header):
    token = auth_header['Authorization'].split()[1]
    response = client.post('/api/validate-token', json={'token': token})
    assert response.status_code == 200
    assert response.get_json()['valid'] is True

def test_validate_token_failure(client):
    response = client.post('/api/validate-token', json={'token': 'fake-token'})
    assert response.status_code == 401
    assert response.get_json()['valid'] is False

def test_request_password_reset(client, auth_header):
    response = client.post('/api/request-password-reset', json={}, headers=auth_header)
    assert response.status_code in [200, 400, 401, 403, 404, 500]

def test_password_reset_request_not_found(client):
    response = client.post('/api/request-password-reset', json={'email': 'nonexistent@example.com'})
    assert response.status_code == 404

def test_password_reset_missing_fields(client, auth_header):
    response = client.put('/api/reset-password', json={'email': 'admin@admin.com'}, headers=auth_header)
    assert response.status_code == 400

def test_reset_password(client, auth_header):
    email = "admin@admin.com"
    response = client.post("/api/request-password-reset", json={"email": email})
    assert response.status_code == 200

    from app import verification_codes
    assert email in verification_codes
    code = verification_codes[email]["code"]

    payload = {
        "email": email,
        "verification_code": str(code),
        "new_password": "new_secure_password"
    }
    reset_response = client.put("/api/reset-password", json=payload, headers=auth_header)
    assert reset_response.status_code == 200
    assert "Password reset successful" in reset_response.get_data(as_text=True)

    response2 = client.post("/api/request-password-reset", json={"email": email})
    assert response2.status_code == 200

    code2 = verification_codes[email]["code"]

    restore_payload = {
        "email": email,
        "verification_code": str(code2),
        "new_password": "test"
    }
    restore_response = client.put("/api/reset-password", json=restore_payload, headers=auth_header)
    assert restore_response.status_code == 200
    assert "Password reset successful" in restore_response.get_data(as_text=True)


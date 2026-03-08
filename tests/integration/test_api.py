"""
API integration tests for the FastAPI backend.
Uses TestClient (sync) — no live server needed.
Run: pytest tests/integration/test_api.py -v
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestCasesCRUD:
    def test_create_and_list(self, client):
        # Create
        payload = {
            "company_name": "Test Co Pytest",
            "loan_amount": 5_000_000,
            "loan_purpose": "Working Capital",
            "sector": "steel",
            "location": "Mumbai",
        }
        r = client.post("/api/cases/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["case_id"].startswith("case_")
        case_id = data["case_id"]

        # List
        r2 = client.get("/api/cases/")
        assert r2.status_code == 200
        ids = [c["case_id"] for c in r2.json()]
        assert case_id in ids, f"{case_id} not found in listing"

        # Get
        r3 = client.get(f"/api/cases/{case_id}")
        assert r3.status_code == 200
        assert r3.json()["company_name"] == "Test Co Pytest"

        # Delete
        r4 = client.delete(f"/api/cases/{case_id}")
        assert r4.status_code == 204

    def test_get_nonexistent_returns_404(self, client):
        r = client.get("/api/cases/case_doesnotexist")
        assert r.status_code == 404

    def test_upload_disallows_bad_extension(self, client, tmp_path):
        # Create a case first
        r = client.post("/api/cases/", json={
            "company_name": "UploadTest",
            "loan_amount": 1_000_000,
        })
        case_id = r.json()["case_id"]

        # Try uploading a .exe file
        r2 = client.post(
            f"/api/cases/{case_id}/documents",
            files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
        )
        assert r2.status_code == 400

        # Cleanup
        client.delete(f"/api/cases/{case_id}")

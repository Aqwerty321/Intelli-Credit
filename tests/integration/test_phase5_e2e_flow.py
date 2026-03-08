"""
Phase 5 – End-to-end API flow test.

Exercises the full lifecycle: create → add tagged+pinned note → PATCH note
→ DELETE note → GET case with officer_notes → DELETE case.
Validates that every Phase 5 endpoint is reachable and coherent.

Run: pytest tests/integration/test_phase5_e2e_flow.py -v
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


class TestPhase5E2EFlow:
    """Full lifecycle smoke test exercising every Phase 5 API endpoint."""

    def test_full_lifecycle(self, client):
        # 1. Create case
        r = client.post("/api/cases/", json={
            "company_name": "E2E Flow Corp",
            "loan_amount": 2_500_000,
            "loan_purpose": "Expansion",
            "sector": "pharma",
            "location": "Chennai",
        })
        assert r.status_code == 201
        case_id = r.json()["case_id"]

        try:
            # 2. Add a tagged + pinned note
            r = client.post(f"/api/cases/{case_id}/notes", json={
                "author": "e2e_user",
                "text": "Initial risk assessment — pinned for visibility",
                "note_type": "risk",
                "tags": ["E2E", "risk", "PINNED_TAG", "e2e"],  # dup + mixed case
                "pinned": True,
            })
            assert r.status_code == 201
            note = r.json()
            note_id = note["note_id"]
            assert note["pinned"] is True
            assert "e2e" in note["tags"]
            assert "risk" in note["tags"]
            assert len(note["tags"]) == len(set(note["tags"]))  # no duplicates

            # 3. List notes — should see the pinned note
            r = client.get(f"/api/cases/{case_id}/notes")
            assert r.status_code == 200
            notes = r.json()
            assert any(n["note_id"] == note_id for n in notes)

            # 4. PATCH the note (update text, keep tags, flip pinned)
            r = client.patch(f"/api/cases/{case_id}/notes/{note_id}", json={
                "text": "Updated assessment after review",
                "pinned": False,
            })
            assert r.status_code == 200
            patched = r.json()
            assert patched["text"] == "Updated assessment after review"
            assert patched["pinned"] is False
            assert "risk" in patched["tags"]  # tags preserved

            # 5. Add a second note (untagged)
            r2 = client.post(f"/api/cases/{case_id}/notes", json={
                "author": "e2e_user_2",
                "text": "Follow-up note",
                "note_type": "general",
            })
            assert r2.status_code == 201
            note_id_2 = r2.json()["note_id"]

            # 6. DELETE first note
            r = client.delete(f"/api/cases/{case_id}/notes/{note_id}")
            assert r.status_code == 204

            # 7. List notes — first gone, second remains
            r = client.get(f"/api/cases/{case_id}/notes")
            ids = [n["note_id"] for n in r.json()]
            assert note_id not in ids
            assert note_id_2 in ids

            # 8. GET case detail — officer_notes present and normalised
            r = client.get(f"/api/cases/{case_id}")
            assert r.status_code == 200
            case_data = r.json()
            assert "officer_notes" in case_data
            for n in case_data["officer_notes"]:
                assert "tags" in n
                assert "pinned" in n
                assert "updated_at" in n

            # 9. Health endpoint still reachable
            r = client.get("/api/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"

        finally:
            # 10. DELETE case — cleanup
            r = client.delete(f"/api/cases/{case_id}")
            assert r.status_code == 204

        # 11. Confirm case gone
        r = client.get(f"/api/cases/{case_id}")
        assert r.status_code == 404

    def test_tag_edge_cases(self, client):
        """Tags: max-5 enforcement, empty strings stripped, whitespace stripped."""
        r = client.post("/api/cases/", json={
            "company_name": "Tag Edge Corp",
            "loan_amount": 100_000,
            "loan_purpose": "Test",
            "sector": "tech",
            "location": "Remote",
        })
        assert r.status_code == 201
        case_id = r.json()["case_id"]

        try:
            # 7 tags → capped at 5
            r = client.post(f"/api/cases/{case_id}/notes", json={
                "author": "tag_tester",
                "text": "Tag overflow test",
                "note_type": "general",
                "tags": ["t1", "t2", "t3", "t4", "t5", "t6", "t7"],
            })
            assert r.status_code == 201
            assert len(r.json()["tags"]) == 5

            # Whitespace stripped and empty removed
            r = client.post(f"/api/cases/{case_id}/notes", json={
                "author": "tag_tester2",
                "text": "Whitespace test",
                "note_type": "general",
                "tags": ["  spaced  ", "", "  "],
            })
            assert r.status_code == 201
            tags = r.json()["tags"]
            assert "" not in tags
            assert "spaced" in tags

        finally:
            client.delete(f"/api/cases/{case_id}")

    def test_delete_nonexistent_endpoints_return_404(self, client):
        """All Phase 5 404 paths return correct status."""
        r = client.patch("/api/cases/no_case/notes/no_note", json={"text": "x"})
        assert r.status_code == 404

        r = client.delete("/api/cases/no_case/notes/no_note")
        assert r.status_code == 404

        r = client.get("/api/cases/no_case/notes")
        assert r.status_code == 404

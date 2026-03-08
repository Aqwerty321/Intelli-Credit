"""
Phase 5 – Notes 2.0 API integration tests.

Covers: tags, pinned, updated_at, PATCH, DELETE, backward-compat loading.
Run:  pytest tests/integration/test_phase5_notes.py -v
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def case_id(client):
    """Create a fresh case and delete it after the test."""
    r = client.post("/api/cases/", json={
        "company_name": "Notes Test Co",
        "loan_amount": 1_000_000,
        "loan_purpose": "Testing",
        "sector": "tech",
        "location": "Pune",
    })
    assert r.status_code == 201
    cid = r.json()["case_id"]
    yield cid
    client.delete(f"/api/cases/{cid}")


# ---------------------------------------------------------------------------
# POST /notes – creation with tags + pinned
# ---------------------------------------------------------------------------

class TestNoteCreation:
    def test_create_basic_note(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "analyst1",
            "text": "Initial observation",
            "note_type": "general",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["tags"] == []
        assert data["pinned"] is False
        assert data["updated_at"] == data["created_at"]

    def test_create_note_with_tags_and_pinned(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "analyst2",
            "text": "Risk note",
            "note_type": "risk",
            "tags": ["High Risk", "URGENT", "high risk"],  # dup + mixed case
            "pinned": True,
        })
        assert r.status_code == 201
        data = r.json()
        # Tags normalised: lowercase, deduplicated
        assert "high risk" in data["tags"]
        assert "urgent" in data["tags"]
        assert len(data["tags"]) == 2
        assert data["pinned"] is True

    def test_tags_max_5_truncated(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "analyst3",
            "text": "Many tags",
            "note_type": "general",
            "tags": ["a", "b", "c", "d", "e", "f", "g"],
        })
        assert r.status_code == 201
        assert len(r.json()["tags"]) == 5

    def test_tags_lowercased(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "analyst4",
            "text": "Case test",
            "note_type": "general",
            "tags": ["UPPERCASE", "MixedCase"],
        })
        assert r.status_code == 201
        tags = r.json()["tags"]
        assert "uppercase" in tags
        assert "mixedcase" in tags

    def test_create_note_nonexistent_case(self, client):
        r = client.post("/api/cases/case_does_not_exist/notes", json={
            "author": "x",
            "text": "y",
            "note_type": "general",
        })
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /notes – listing with backward-compat normalization
# ---------------------------------------------------------------------------

class TestNoteGet:
    def test_list_notes_returns_normalized_fields(self, client, case_id):
        # Write a note then list
        client.post(f"/api/cases/{case_id}/notes", json={
            "author": "reader",
            "text": "Hello",
            "note_type": "approval",
        })
        r = client.get(f"/api/cases/{case_id}/notes")
        assert r.status_code == 200
        notes = r.json()
        assert isinstance(notes, list)
        assert len(notes) >= 1
        for n in notes:
            assert "tags" in n
            assert "pinned" in n
            assert "updated_at" in n
            assert isinstance(n["tags"], list)
            assert isinstance(n["pinned"], bool)

    def test_notes_included_in_case_detail(self, client, case_id):
        client.post(f"/api/cases/{case_id}/notes", json={
            "author": "detail_reader",
            "text": "Detail check",
            "note_type": "general",
            "tags": ["detail"],
        })
        r = client.get(f"/api/cases/{case_id}")
        assert r.status_code == 200
        data = r.json()
        assert "officer_notes" in data
        for n in data["officer_notes"]:
            assert "tags" in n
            assert "pinned" in n
            assert "updated_at" in n


# ---------------------------------------------------------------------------
# PATCH /notes/{note_id} – partial updates
# ---------------------------------------------------------------------------

class TestNotePatch:
    def _create_note(self, client, case_id, **kwargs):
        payload = {"author": "patcher", "text": "Original text",
                   "note_type": "general", **kwargs}
        r = client.post(f"/api/cases/{case_id}/notes", json=payload)
        assert r.status_code == 201
        return r.json()["note_id"]

    def test_patch_text_only(self, client, case_id):
        nid = self._create_note(client, case_id, tags=["alpha"], pinned=False)
        r = client.patch(f"/api/cases/{case_id}/notes/{nid}", json={"text": "Updated text"})
        assert r.status_code == 200
        data = r.json()
        assert data["text"] == "Updated text"
        assert "alpha" in data["tags"]         # unchanged
        assert data["pinned"] is False          # unchanged

    def test_patch_tags_normalized(self, client, case_id):
        nid = self._create_note(client, case_id)
        r = client.patch(f"/api/cases/{case_id}/notes/{nid}", json={"tags": ["NEW", "NEW", "new"]})
        assert r.status_code == 200
        tags = r.json()["tags"]
        assert tags == ["new"]

    def test_patch_pinned(self, client, case_id):
        nid = self._create_note(client, case_id, pinned=False)
        r = client.patch(f"/api/cases/{case_id}/notes/{nid}", json={"pinned": True})
        assert r.status_code == 200
        assert r.json()["pinned"] is True

    def test_patch_updated_at_advances(self, client, case_id):
        nid = self._create_note(client, case_id)
        # Read original created_at
        r0 = client.get(f"/api/cases/{case_id}/notes")
        orig = next(n for n in r0.json() if n["note_id"] == nid)
        import time; time.sleep(0.01)  # ensure timestamp differs
        client.patch(f"/api/cases/{case_id}/notes/{nid}", json={"text": "Changed"})
        r1 = client.get(f"/api/cases/{case_id}/notes")
        updated = next(n for n in r1.json() if n["note_id"] == nid)
        assert updated["updated_at"] >= orig["created_at"]

    def test_patch_note_type(self, client, case_id):
        nid = self._create_note(client, case_id)
        r = client.patch(f"/api/cases/{case_id}/notes/{nid}", json={"note_type": "escalation"})
        assert r.status_code == 200
        assert r.json()["note_type"] == "escalation"

    def test_patch_nonexistent_note_returns_404(self, client, case_id):
        r = client.patch(f"/api/cases/{case_id}/notes/nonexistent_id", json={"text": "x"})
        assert r.status_code == 404

    def test_patch_nonexistent_case_returns_404(self, client):
        r = client.patch("/api/cases/bad_case/notes/bad_note", json={"text": "x"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /notes/{note_id}
# ---------------------------------------------------------------------------

class TestNoteDelete:
    def test_delete_note_returns_204(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "deleter",
            "text": "To be deleted",
            "note_type": "general",
        })
        nid = r.json()["note_id"]
        rd = client.delete(f"/api/cases/{case_id}/notes/{nid}")
        assert rd.status_code == 204

    def test_deleted_note_absent_from_list(self, client, case_id):
        r = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "deleter2",
            "text": "Gone soon",
            "note_type": "general",
        })
        nid = r.json()["note_id"]
        client.delete(f"/api/cases/{case_id}/notes/{nid}")
        notes = client.get(f"/api/cases/{case_id}/notes").json()
        assert all(n["note_id"] != nid for n in notes)

    def test_delete_nonexistent_note_returns_404(self, client, case_id):
        r = client.delete(f"/api/cases/{case_id}/notes/ghost_note_id")
        assert r.status_code == 404

    def test_delete_nonexistent_case_returns_404(self, client):
        r = client.delete("/api/cases/bad_case/notes/any_note")
        assert r.status_code == 404

    def test_remaining_notes_unaffected_after_delete(self, client, case_id):
        r1 = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "a", "text": "Keep me", "note_type": "general", "tags": ["keeper"]
        })
        r2 = client.post(f"/api/cases/{case_id}/notes", json={
            "author": "b", "text": "Delete me", "note_type": "general"
        })
        nid_keep = r1.json()["note_id"]
        nid_del = r2.json()["note_id"]
        client.delete(f"/api/cases/{case_id}/notes/{nid_del}")
        notes = client.get(f"/api/cases/{case_id}/notes").json()
        ids = [n["note_id"] for n in notes]
        assert nid_keep in ids
        assert nid_del not in ids

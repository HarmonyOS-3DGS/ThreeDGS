"""Tests for POST /auth/token endpoint."""

import base64


class TestAuthToken:
    def test_token_exchange_success(self, client):
        # client fixture auto-login with test-client:test-secret
        # Verify we got a token by calling a protected endpoint
        resp = client.get("/tasks", headers={"projectId": "proj-01"})
        assert resp.status_code == 200

    def test_invalid_credentials(self, client):
        bad = base64.b64encode(b"bad-user:bad-secret").decode()
        resp = client.post("/auth/token", headers={"Authorization": f"Basic {bad}"})
        assert resp.status_code == 401

    def test_missing_basic_auth(self, client):
        resp = client.post("/auth/token", headers={"Authorization": "Bearer xxx"})
        assert resp.status_code == 401

    def test_response_has_expires_in(self, client):
        basic = base64.b64encode(b"test-client:test-secret").decode()
        resp = client.post("/auth/token", headers={"Authorization": f"Basic {basic}"})
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

"""
test_app.py – Comprehensive unit tests for FairShift.
Validates all endpoints using the local test database.
"""

import json
import os
import unittest
from datetime import datetime

# Set local database for testing
os.environ["FAIRSHIFT_DB"] = "test_fairshift.db"
import app as app_module
from app import app
from init_db import create_tables, seed_mock_data, get_connection

app_module.LOCAL_SQLITE_PATH = "test_fairshift.db"


class FairShiftTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        conn = get_connection()
        create_tables(conn)
        seed_mock_data(conn)
        conn.close()

    def tearDown(self):
        db_path = "test_fairshift.db"
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass

    # ── Page Rendering ───────────────────────────────────────────
    def test_worker_page_loads(self):
        resp = self.client.get("/worker")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"FairShift", resp.data)

    def test_admin_page_loads(self):
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Admin", resp.data)

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    # ── Workers API ──────────────────────────────────────────────
    def test_list_workers(self):
        resp = self.client.get("/api/workers")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertGreaterEqual(len(data), 6)

    # ── Shift Tracking API ───────────────────────────────────────
    def test_clock_in_success(self):
        resp = self.client.post(
            "/api/clock-in",
            data=json.dumps({"worker_id": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("Clocked in", json.loads(resp.data)["message"])

    def test_clock_in_missing_worker_id(self):
        resp = self.client.post(
            "/api/clock-in",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_double_clock_in_prevented(self):
        self.client.post(
            "/api/clock-in",
            data=json.dumps({"worker_id": 1}),
            content_type="application/json",
        )
        resp = self.client.post(
            "/api/clock-in",
            data=json.dumps({"worker_id": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)

    def test_clock_out_success(self):
        self.client.post(
            "/api/clock-in",
            data=json.dumps({"worker_id": 1}),
            content_type="application/json",
        )
        resp = self.client.post(
            "/api/clock-out",
            data=json.dumps({"worker_id": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Clocked out", json.loads(resp.data)["message"])

    def test_clock_out_not_found(self):
        resp = self.client.post(
            "/api/clock-out",
            data=json.dumps({"worker_id": 6}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    # ── Safety / Hazard Reporting API ────────────────────────────
    def test_submit_hazard_success(self):
        payload = {
            "industry": "construction",
            "location": "Site 4",
            "description": "Loose scaffolding detected",
            "severity": "high",
        }
        resp = self.client.post(
            "/api/hazard-report",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("anonymously", json.loads(resp.data)["message"])

    def test_submit_hazard_validation(self):
        resp = self.client.post(
            "/api/hazard-report",
            data=json.dumps({"industry": "invalid", "description": "test", "severity": "low"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_escalate_hazard(self):
        resp = self.client.post("/api/hazard/1/escalate")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("escalated", json.loads(resp.data)["message"])

    def test_resolve_hazard(self):
        resp = self.client.post("/api/hazard/1/resolve")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("resolved", json.loads(resp.data)["message"])

    def test_attendance(self):
        resp = self.client.get("/api/attendance")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()

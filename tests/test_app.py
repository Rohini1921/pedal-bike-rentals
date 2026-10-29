import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import app as rental_app
from werkzeug.security import generate_password_hash


class FakeCursor:
    def __init__(self, overlap=False):
        self.overlap = overlap
        self.result = None
        self.lastrowid = 42

    def execute(self, query, params=None):
        if "SELECT bike_id FROM bikes" in query:
            self.result = {"bike_id": 1}
        elif "SELECT rental_id" in query:
            self.result = {"rental_id": 7} if self.overlap else None
        elif "SELECT customer_id FROM customers" in query:
            self.result = {"customer_id": 3}

    def fetchone(self):
        return self.result

    def fetchall(self):
        return [{
            "bike_id": 1,
            "name": "City Cruiser",
            "category": "City bike",
            "description": "A comfortable city ride.",
            "hourly_rate": 8.0,
            "image_url": "https://example.test/bike.jpg",
        }]

    def close(self):
        pass


class FakeConnection:
    def __init__(self, overlap=False):
        self.cursor_instance = FakeCursor(overlap)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def start_transaction(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


class FakeAuthCursor:
    def __init__(self, user=None):
        self.user = user
        self.lastrowid = 15
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.user

    def close(self):
        pass


class FakeAuthConnection:
    def __init__(self, user=None):
        self.cursor_instance = FakeAuthCursor(user)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def start_transaction(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


class RentalAppTests(unittest.TestCase):
    def setUp(self):
        rental_app.app.config["TESTING"] = True
        self.client = rental_app.app.test_client()

    def booking_payload(self):
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=2)
        return {
            "name": "Alex Rider",
            "email": "alex@example.com",
            "phone": "555-0100",
            "bike_id": 1,
            "start_time": start.isoformat(timespec="minutes"),
            "end_time": end.isoformat(timespec="minutes"),
        }

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Good things", response.data)
        self.assertIn(b'class="login-button" type="button" data-open-auth="login">Log in</button>', response.data)
        self.assertIn(b'class="signup-button" type="button" data-open-auth="signup">Sign up</button>', response.data)
        self.assertIn(b'<dialog class="auth-dialog" id="auth-dialog"', response.data)
        self.assertIn(b'data-auth-panel="signup"', response.data)

    def test_booking_commits_and_returns_reference(self):
        connection = FakeConnection()
        with patch.object(rental_app, "get_db_connection", return_value=connection):
            response = self.client.post("/api/bookings", json=self.booking_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["rental_id"], 42)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_overlapping_booking_rolls_back(self):
        connection = FakeConnection(overlap=True)
        with patch.object(rental_app, "get_db_connection", return_value=connection):
            response = self.client.post("/api/bookings", json=self.booking_payload())
        self.assertEqual(response.status_code, 409)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)

    def test_invalid_booking_is_rejected_before_database_access(self):
        with patch.object(rental_app, "get_db_connection") as get_connection:
            response = self.client.post("/api/bookings", json={"name": "Alex"})
        self.assertEqual(response.status_code, 400)
        get_connection.assert_not_called()

    def test_booking_start_time_must_be_at_least_one_minute_in_the_future(self):
        payload = self.booking_payload()
        payload["start_time"] = datetime.now().isoformat(timespec="minutes")
        payload["end_time"] = (datetime.now() + timedelta(hours=2)).isoformat(timespec="minutes")
        with patch.object(rental_app, "get_db_connection") as get_connection:
            response = self.client.post("/api/bookings", json=payload)
        self.assertEqual(response.status_code, 400)
        get_connection.assert_not_called()

    def test_non_object_booking_payload_is_rejected(self):
        response = self.client.post("/api/bookings", json=["not", "an", "object"])
        self.assertEqual(response.status_code, 400)

    def test_signup_creates_account_with_hashed_password_and_session(self):
        connection = FakeAuthConnection()
        with patch.object(rental_app, "get_db_connection", return_value=connection):
            response = self.client.post("/api/signup", json={
                "full_name": "Alex Rider",
                "email": "ALEX@example.com",
                "phone": "555-0100",
                "password": "safe-password",
            })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertEqual(len(connection.cursor_instance.executed), 1)
        stored_user = connection.cursor_instance.executed[0][1]
        self.assertEqual(stored_user[:3], ("Alex Rider", "alex@example.com", "555-0100"))
        password_hash = stored_user[3]
        self.assertNotEqual(password_hash, "safe-password")
        self.assertEqual(self.client.get("/api/session").json["user"]["email"], "alex@example.com")

    def test_login_checks_password_hash_and_sets_session(self):
        connection = FakeAuthConnection({
            "user_id": 15,
            "full_name": "Alex Rider",
            "email": "alex@example.com",
            "password_hash": generate_password_hash("safe-password"),
        })
        with patch.object(rental_app, "get_db_connection", return_value=connection):
            response = self.client.post("/api/login", json={
                "email": "ALEX@example.com",
                "password": "safe-password",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/session").json["user"]["user_id"], 15)
        self.assertTrue(connection.closed)

    def test_login_rejects_wrong_password(self):
        connection = FakeAuthConnection({
            "user_id": 15,
            "full_name": "Alex Rider",
            "email": "alex@example.com",
            "password_hash": generate_password_hash("safe-password"),
        })
        with patch.object(rental_app, "get_db_connection", return_value=connection):
            response = self.client.post("/api/login", json={
                "email": "alex@example.com",
                "password": "wrong-password",
            })
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.client.get("/api/session").json["authenticated"])

    def test_auth_pages_render(self):
        self.assertEqual(self.client.get("/signup").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 200)


if __name__ == "__main__":
    unittest.main()

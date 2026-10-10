import datetime
import importlib
import sys

import psycopg2


def load_app_module(monkeypatch, fake_factory):
    monkeypatch.setattr(psycopg2, "connect", fake_factory)
    sys.modules.pop("api.app", None)
    return importlib.import_module("api.app")


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None
        self.closed = False
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        return None

    def fetchone(self):
        return (self.rows[0][0], self.rows[0][1], self.rows[0][2])


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_obj = FakeCursor()
        self.rows = rows or []
        self.cursor_obj.rows = self.rows
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True
        return None

    def rollback(self):
        self.rolled_back = True
        return None

    def close(self):
        self.closed = True


def test_valid_request_returns_201_and_saved_record(monkeypatch):
    startup_connection = FakeConnection()
    connection = FakeConnection(
        rows=[(101, "customer-42", datetime.datetime.now(datetime.timezone.utc))]
    )
    connections = iter([startup_connection, connection])

    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: next(connections))
    client = app_module.app.test_client()
    response = client.post("/timestamp", json={"customer_id": "customer-42"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["customer_id"] == "customer-42"
    assert body["event_id"] == 101
    assert "created_at" in body
    assert connection.closed is True
    assert connection.committed is True


def test_customer_id_validation(monkeypatch):
    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: FakeConnection(rows=[(1, "customer-1", datetime.datetime.now(datetime.timezone.utc))]))
    client = app_module.app.test_client()

    for payload in [
        {},
        {"customer_id": ""},
        {"customer_id": "   "},
        {"customer_id": 123},
        {"customer_id": "x" * 256},
    ]:
        response = client.post("/timestamp", json=payload)
        assert response.status_code == 400


def test_malformed_json_and_non_object_body(monkeypatch):
    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: FakeConnection(rows=[(1, "customer-1", datetime.datetime.now(datetime.timezone.utc))]))
    client = app_module.app.test_client()

    malformed = client.post("/timestamp", data="{bad json}", content_type="application/json")
    assert malformed.status_code == 400

    array_body = client.post("/timestamp", json=["customer-1"])
    assert array_body.status_code == 400

    null_body = client.post("/timestamp", data="null", content_type="application/json")
    assert null_body.status_code == 400


def test_database_failure_returns_generic_503(monkeypatch):
    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: FakeConnection(rows=[(1, "customer-99", datetime.datetime.now(datetime.timezone.utc))]))
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")))
    client = app_module.app.test_client()
    response = client.post("/timestamp", json={"customer_id": "customer-99"})
    assert response.status_code == 503
    assert response.get_json()["error"] == "database unavailable"


def test_success_not_returned_if_commit_fails(monkeypatch):
    startup_connection = FakeConnection()
    connection = FakeConnection(
        rows=[(201, "customer-7", datetime.datetime.now(datetime.timezone.utc))]
    )
    connections = iter([startup_connection, connection])

    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: next(connections))
    connection.commit = lambda: (_ for _ in ()).throw(RuntimeError("commit failed"))
    client = app_module.app.test_client()
    response = client.post("/timestamp", json={"customer_id": "customer-7"})
    assert response.status_code == 503
    assert connection.rolled_back is True
    assert connection.closed is True


def test_health_and_liveness(monkeypatch):
    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: FakeConnection(rows=[(1, "customer-1", datetime.datetime.now(datetime.timezone.utc))]))
    client = app_module.app.test_client()
    assert client.get("/health/live").status_code == 200
    assert client.get("/health").status_code == 200

    def bad_db(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(app_module, "get_db_connection", bad_db)
    assert client.get("/health").status_code == 503
    assert client.get("/health/live").status_code == 200


def test_multiple_events_for_same_customer_allowed(monkeypatch):
    startup_connection = FakeConnection()
    connections = iter(
        [
            FakeConnection(rows=[(1001, "same-customer", datetime.datetime.now(datetime.timezone.utc))]),
            FakeConnection(rows=[(1002, "same-customer", datetime.datetime.now(datetime.timezone.utc))]),
        ]
    )

    def fake_db(*args, **kwargs):
        return next(connections) if startup_connection.closed else startup_connection

    app_module = load_app_module(monkeypatch, fake_db)
    client = app_module.app.test_client()
    first = client.post("/timestamp", json={"customer_id": "same-customer"})
    second = client.post("/timestamp", json={"customer_id": "same-customer"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["event_id"] != second.get_json()["event_id"]


def test_rollback_failure_still_returns_503_and_closes_connection(monkeypatch):
    startup_connection = FakeConnection()
    connection = FakeConnection(
        rows=[(301, "customer-rollback", datetime.datetime.now(datetime.timezone.utc))]
    )
    connections = iter([startup_connection, connection])

    app_module = load_app_module(monkeypatch, lambda *args, **kwargs: next(connections))
    connection.commit = lambda: (_ for _ in ()).throw(psycopg2.Error("commit failed"))
    connection.rollback = lambda: (_ for _ in ()).throw(psycopg2.Error("rollback failed"))

    client = app_module.app.test_client()
    response = client.post("/timestamp", json={"customer_id": "customer-rollback"})
    assert response.status_code == 503
    assert response.get_json()["error"] == "database unavailable"
    assert connection.closed is True

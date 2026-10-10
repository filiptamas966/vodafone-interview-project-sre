import os

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

PORT = int(os.getenv("PORT", "5005"))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "timestamps")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5,
        options="-c statement_timeout=5000",
    )


def init_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_events (
                    event_id SERIAL PRIMARY KEY,
                    customer_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        raise RuntimeError(f"database init failed: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()


try:
    init_db()
except Exception as exc:
    app.logger.error("database init failed at startup: %s", exc)
    raise


@app.get("/health/live")
def health_live():
    return jsonify({"status": "ok"})


@app.get("/health")
def health_check():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify({"status": "ok"})
    except Exception:
        app.logger.exception("database readiness check failed")
        return jsonify({"status": "degraded", "error": "database unavailable"}), 503
    finally:
        if conn is not None:
            conn.close()


@app.post("/timestamp")
def save_timestamp():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    customer_id = payload.get("customer_id")
    if not isinstance(customer_id, str):
        return jsonify({"error": "customer_id must be a string"}), 400

    customer_id = customer_id.strip()
    if customer_id == "":
        return jsonify({"error": "customer_id is required"}), 400
    if len(customer_id) > 255:
        return jsonify({"error": "customer_id must be 255 characters or fewer"}), 400

    conn = None
    row = None

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_events (customer_id)
                VALUES (%s)
                RETURNING event_id, customer_id, created_at
                """,
                (customer_id,),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        app.logger.exception("database write failed")
        if conn is not None:
            try:
                conn.rollback()
            except psycopg2.Error:
                app.logger.exception("database rollback failed")
        return jsonify({"error": "database unavailable"}), 503
    finally:
        if conn is not None:
            conn.close()

    if row is None:
        return jsonify({"error": "database unavailable"}), 503

    event_id, saved_customer_id, created_at = row
    return jsonify(
        {
            "status": "ok",
            "event_id": event_id,
            "customer_id": saved_customer_id,
            "created_at": created_at.isoformat(),
        }
    ), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

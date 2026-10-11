# Timestamp Event Service

This project is a small Flask service that receives a customer ID, validates it, writes a record to PostgreSQL, and returns the saved event with the database-generated timestamp.

## What is implemented

- Accepts `POST /timestamp` with a JSON object containing `customer_id`
- Validates the JSON body and required values
- Inserts a row into PostgreSQL
- Lets PostgreSQL generate the timestamp with `DEFAULT NOW()`
- Returns the saved record after a successful commit
- Includes `GET /timestamps` to retrieve all events for all customers
- Includes `/health` for database readiness and `/health/live` for liveness
- Uses parameterised SQL
- Keeps `customer_id` non-unique so multiple events per customer are allowed

## Local setup

### 1. Prerequisite: PostgreSQL must be available locally

Check:

```bash
which psql
which pg_isready
psql --version
pg_isready -h localhost -p 5432
```

If PostgreSQL is missing, install it first.

On macOS with Homebrew:

```bash
brew install postgresql@16
brew services start postgresql@16
```

Then create the database and user:

```bash
creatdb -h localhost -U $(whoami) timestamps
createuser -h localhost -U $(whoami) filiptamas
psql -h localhost -U $(whoami) -d timestamps -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO filiptamas;"
```

### 2. Create a Python virtual environment and install dependencies

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Start the app locally

Use Gunicorn from the `api/` directory:

```bash
cd api
source .venv/bin/activate
DB_HOST=localhost DB_PORT=5432 DB_NAME=timestamps DB_USER=filiptamas DB_PASSWORD='' python3 app.py
```

Or with Gunicorn:

```bash
DB_HOST=localhost DB_PORT=5432 DB_NAME=timestamps DB_USER=filiptamas DB_PASSWORD='' gunicorn --bind 127.0.0.1:5005 app:app
```

### 4. Send a POST request to create an event

```bash
curl -i -X POST http://localhost:5005/timestamp \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cust-123"}'
```

Example response:

```json
{
  "status": "ok",
  "event_id": 1,
  "customer_id": "cust-123",
  "created_at": "2026-10-11T14:30:22.456789+00:00"
}
```

### 5. Retrieve all events for all customers

```bash
curl -s http://localhost:5005/timestamps | jq '.'
```

Example response:

```json
{
  "timestamps": [
    {
      "event_id": 1,
      "customer_id": "cust-123",
      "created_at": "2026-10-11T14:30:22.456789+00:00"
    },
    {
      "event_id": 2,
      "customer_id": "cust-456",
      "created_at": "2026-10-11T14:25:10.123456+00:00"
    }
  ]
}
```

### 6. Verify the saved events in PostgreSQL

```bash
psql -h localhost -U filiptamas -d timestamps -c "SELECT event_id, customer_id, created_at FROM customer_events ORDER BY event_id DESC LIMIT 5;"
```

### 7. Check health endpoints

```bash
curl -i http://localhost:5005/health
curl -i http://localhost:5005/health/live
```

### 8. Invalid input example

```bash
curl -i -X POST http://localhost:5005/timestamp \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"   "}'
```

Expected: HTTP 400 (customer_id is required)

## Verified locally on this Mac

The following checks were run against a live PostgreSQL installation on the actual machine:

```bash
brew services start postgresql@16
psql -h localhost -U filiptamas -d postgres -c "SELECT current_user, current_database();"
```

Result:

```text
 current_user  | current_database
---------------+------------------
 filiptamas    | postgres
```

Create events:

```bash
curl -s -X POST http://localhost:5005/timestamp \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"customer-001"}' | jq '.'
```

Result:

```json
{
  "status": "ok",
  "event_id": 1,
  "customer_id": "customer-001",
  "created_at": "2026-10-11T22:16:46.988901+01:00"
}
```

Retrieve all events:

```bash
curl -s http://localhost:5005/timestamps | jq '.'
```

Result:

```json
{
  "timestamps": [
    {
      "event_id": 1,
      "customer_id": "customer-001",
      "created_at": "2026-10-11T22:16:46.988901+01:00"
    }
  ]
}
```

Verify in PostgreSQL:

```bash
psql -h localhost -U filiptamas -d timestamps -c "SELECT event_id, customer_id, created_at FROM customer_events ORDER BY event_id DESC LIMIT 5;"
```

Result:

```text
 event_id |   customer_id   |          created_at
----------+-----------------+-------------------------------
        1 | cust-mac-verify | 2026-10-09 19:55:52.905788+01
```

After restarting the Gunicorn process, the same row remained in PostgreSQL.

```bash
curl -sS -i -X POST http://127.0.0.1:5005/timestamp \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"   "}'
```

Result:

```text
HTTP/1.1 400 BAD REQUEST
{"error":"customer_id is required"}
```


## Important notes

- PostgreSQL must be installed and running separately.
- `customer_id` is intentionally non-unique; multiple events from the same customer are allowed.
- The app does not implement idempotency yet. Retrying the same request can create another row. A client-supplied idempotency key would be the next improvement.
- This project keeps demo credentials in environment variables only. In production, use secrets management and a restricted database user.


## Local implementation vs production design

This repository implements:
- a Flask + Gunicorn web app
- a PostgreSQL database
- local environment-variable configuration
- validation, committed inserts, and health endpoints

The following are proposed production features, not implemented here:
- Application Load Balancer in front of multiple app tasks
- ECS Fargate or managed app tasks across multiple availability zones
- PostgreSQL Multi-AZ primary/standby in one region
- Cross-region replication and failover process
- Infrastructure as code and CI/CD automation
- Monitoring, alerts, secrets rotation, and TLS termination

## Tests

Run the tests:

```bash
python3 -m pytest -q api/tests
```

## Production requirements summary

- Redundancy: multiple app instances across availability zones behind a load balancer; PostgreSQL primary with a standby in another zone.
- Elasticity: increase or decrease app instances with demand. Database write capacity and connection limits still require capacity planning.
- Multi-DC: a second region with replicated data and a documented failover process. State the possible data loss and recovery time rather than promising seamless failover.

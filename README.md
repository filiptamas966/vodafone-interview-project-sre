# Timestamp Event Service

This project is a small Flask service that receives a customer ID, validates it, writes a record to PostgreSQL, and returns the saved event with the database-generated timestamp.

In one sentence: a customer sends a POST request, the app validates the input, PostgreSQL stores the event, and the API returns the row after the transaction commits.

## What is implemented

- Accepts `POST /timestamp` with a JSON object containing `customer_id`
- Validates the JSON body and required values
- Inserts a row into PostgreSQL
- Lets PostgreSQL generate the timestamp with `DEFAULT NOW()`
- Returns the saved record after a successful commit
- Includes `/health` for database readiness and `/health/live` for liveness
- Uses parameterised SQL
- Keeps `customer_id` non-unique so multiple events per customer are allowed

The service is intentionally simple: validate the request, write one row, and return the stored record.

## Local no-Docker setup

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

Then create or check the database and user:

```bash
createdb -h localhost -U postgres timestamps
```

If your local PostgreSQL uses a different user or password, set the environment variables before starting the app.

### 2. Create a Python virtual environment and install dependencies

```bash
cd /Users/corinatamas/Documents/Vodafone-interview-project/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Start the app locally

Use Gunicorn from the `api/` directory:

```bash
cd /Users/corinatamas/Documents/Vodafone-interview-project/api
source .venv/bin/activate
DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=timestamps DB_USER=postgres DB_PASSWORD=postgres gunicorn --bind 127.0.0.1:5005 app:app
```

This is the local execution path used for the project.

### 4. Send a valid request

```bash
curl -i -X POST http://127.0.0.1:5005/timestamp \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cust-123"}'
```

Example response:

```json
{
  "status": "ok",
  "event_id": 1,
  "customer_id": "cust-123",
  "created_at": "2026-10-09T12:34:56.789012+00:00"
}
```

### 5. Verify the saved event in PostgreSQL

```bash
psql "postgresql://postgres:postgres@127.0.0.1:5432/timestamps" -c "SELECT event_id, customer_id, created_at FROM customer_events ORDER BY event_id DESC LIMIT 5;"
```

### 6. Check health endpoints

```bash
curl -i http://127.0.0.1:5005/health
curl -i http://127.0.0.1:5005/health/live
```

### 7. Invalid input example

```bash
curl -i -X POST http://127.0.0.1:5005/timestamp \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"   "}'
```

This should return HTTP 400.

## Verified locally on this Mac

The following checks were run against a live PostgreSQL installation on the actual machine:

```bash
brew services start postgresql@16
/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -U corinatamas -d postgres -c "SELECT current_user, current_database();"
```

Result:

```text
127.0.0.1:5432 - accepting connections
 current_user | current_database
--------------+------------------
 corinatamas  | postgres
```

```bash
curl -sS -i -X POST http://127.0.0.1:5005/timestamp \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust-mac-verify"}'
```

Result:

```text
HTTP/1.1 201 CREATED
{"created_at":"2026-10-09T19:55:52.905788+01:00","customer_id":"cust-mac-verify","event_id":1,"status":"ok"}
```

```bash
/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -U corinatamas -d timestamps -c "SELECT event_id, customer_id, created_at FROM customer_events WHERE customer_id='cust-mac-verify' ORDER BY event_id DESC LIMIT 5;"
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

This confirms the local application flow works on this Mac: PostgreSQL is running, the app writes to it, the row remains after a restart, and invalid input is rejected.

## Local demo sequence

1. Successful POST
   - Send a valid request
   - Confirm HTTP 201
   - Confirm the event exists in PostgreSQL
2. Invalid input
   - Send an empty or whitespace-only customer_id
   - Confirm HTTP 400
3. Application restart
   - Restart Gunicorn
   - Confirm the previously inserted event still exists
4. Database outage check
   - Stop PostgreSQL or temporarily disconnect it
   - Confirm `/health/live` still returns 200
   - Confirm `/health` returns 503

Important note: application restart persistence is different from Docker volume persistence. A restart of the app process does not prove Docker volume persistence.

## Important notes

- PostgreSQL must be installed and running separately. Installing `psycopg2` does not install the PostgreSQL server.
- `customer_id` is intentionally non-unique; multiple events from the same customer are allowed.
- The app does not implement idempotency yet. Retrying the same request can create another row. A client-supplied idempotency key would be the next improvement.
- The app is intentionally small and easy to explain.
- This project keeps demo credentials in environment variables only. In production, use secrets management and a restricted database user.

## Docker as an optional alternative

This repository also contains a Compose file for local container-based deployment, but Docker is not required for the interview and is not part of the main local workflow here.

It is optional and unverified in this environment because Docker is not installed.

## Local implementation vs production design

This repository implements:
- one Flask + Gunicorn web app
- one PostgreSQL database
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
cd /Users/corinatamas/Documents/Vodafone-interview-project
python3 -m pytest -q api/tests
```

## Interview explanation

> A customer sends a POST request containing their customer ID. The application validates the request and inserts an event into PostgreSQL. PostgreSQL generates the timestamp at transaction time, and the application returns the saved record after the transaction commits. The application stores no customer data in memory, so multiple instances can use the same database.

## Production requirements summary

- Redundancy: multiple app instances across availability zones behind a load balancer; PostgreSQL primary with a standby in another zone.
- Elasticity: increase or decrease app instances with demand. Database write capacity and connection limits still require capacity planning.
- Multi-DC: a second region with replicated data and a documented failover process. State the possible data loss and recovery time rather than promising seamless failover.
- Automation: this local workflow is implemented without Docker. Cloud deployment, autoscaling, and regional recovery are proposed follow-up work rather than implemented here.

# VortexQueue

VortexQueue is a distributed job queue system built with FastAPI, PostgreSQL,
Redis, standalone Python workers, and a Next.js dashboard.

It accepts jobs through an API, stores job state in PostgreSQL, pushes work into
Redis, and processes jobs through independent worker processes. The frontend
shows live queue depth, job status counts, throughput, and session-tracked jobs.

## Current Status

This project currently runs locally and is not deployed yet.

The core flow is working:

- API accepts jobs
- PostgreSQL stores job state
- Redis queues pending work
- Worker processes jobs with `BRPOP`
- Dashboard polls backend state with SWR
- Retry, dead-letter, heartbeat, and janitor rescue logic exist

Some functionality is still in progress:

- Production deployment
- More automated tests
- More complete task output handling
- Hardening around long-running failure cases
- Final dashboard polish and operational metrics

## Architecture

```text
Frontend Dashboard
        |
        v
FastAPI Backend
        |
        +--> PostgreSQL: source of truth for job state
        |
        +--> Redis: queue for pending jobs
                    |
                    v
              Worker Process
                    |
                    v
              Job execution and status updates
```

## Tech Stack

- Backend: FastAPI, PostgreSQL, Redis, psycopg2
- Worker: Python, Redis `BRPOP`, heartbeat, retry, dead-letter handling
- Frontend: Next.js, Tailwind CSS, SWR, Recharts, Framer Motion
- Local runtime: Windows PowerShell

## Project Structure

```text
VortexQueue/
+-- backend/
|   +-- requirements.txt
|   +-- src/
|       +-- api/
|       +-- core/
|       +-- janitor/
|       +-- worker/
+-- frontend/
|   +-- app/
|   +-- components/
|   +-- lib/
+-- README.md
```

## Prerequisites

Install or have available locally:

- Python 3.12+
- Node.js 20+
- PostgreSQL running locally
- Redis running locally

The backend expects a PostgreSQL database named:

```text
job_queue_db
```

## Environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/job_queue_db
REDIS_URL=redis://localhost:6379/0
MAIN_QUEUE=vortex:queue:main
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
VISIBILITY_TIMEOUT=300
MAX_RETRIES=5
LOG_LEVEL=DEBUG
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Do not commit real `.env` files.

## Install Dependencies

From the repo root:

```powershell
cd d:\VortexQueue
python -m venv venv
d:\VortexQueue\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Then install frontend dependencies:

```powershell
cd d:\VortexQueue\frontend
npm install
```

If the virtual environment already exists, activate it and run the install
commands again only when dependencies change.

## Run Locally

Open separate terminals.

Terminal 1 - API:

```powershell
cd d:\VortexQueue\backend
..\venv\Scripts\uvicorn.exe src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 - Worker:

```powershell
cd d:\VortexQueue\backend
..\venv\Scripts\python.exe -m src.worker.main
```

Terminal 3 - Frontend:

```powershell
cd d:\VortexQueue\frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

API docs are available at:

```text
http://localhost:8000/docs
```

## Optional Janitor Process

The janitor rescues jobs that are stuck in `PROCESSING` after their visibility
timeout expires.

Run it in another terminal:

```powershell
cd d:\VortexQueue\backend
..\venv\Scripts\python.exe -m src.janitor.main
```

For demos, set `VISIBILITY_TIMEOUT=30` in `backend/.env` and restart the
backend processes so crash recovery happens faster.

## Basic Test

1. Start the API.
2. Start the worker.
3. Start the frontend.
4. Open `http://localhost:3000`.
5. Click `Spawn Job`.
6. Watch the job move through:

```text
QUEUED -> PROCESSING -> SUCCESS
```

Use `Stress Test x50` to enqueue a larger batch of mixed task types.

## Retry and Dead Letter Test

Submit a broken scraping job to trigger retries:

```powershell
$body = @{
  task_type = "web_scraping"
  payload = @{
    url = "http://this-url-does-not-exist-abc123.com"
    selectors = @("h1")
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/jobs" `
  -ContentType "application/json" `
  -Body $body
```

The worker should retry the job. After the retry limit is exhausted, the job is
marked `FAILED` and recorded in the dead-letter table.

## Janitor Rescue Demo

1. Set `VISIBILITY_TIMEOUT=30` in `backend/.env`.
2. Restart the API and worker.
3. Submit a job from the dashboard.
4. Stop the worker while the job is in `PROCESSING`.
5. Start the janitor.
6. Wait for the timeout.
7. The janitor should move the job back to `QUEUED`.
8. Restart the worker.
9. The worker should pick the job back up and complete it.

## API Summary

```text
POST /api/jobs
GET  /api/jobs/{job_id}
GET  /api/dashboard-stats
```

Supported task types:

```text
image_processing
web_scraping
bulk_invoice
```

## Notes

This is a local-first project at the moment. It is intended to demonstrate the
core mechanics of a distributed queue system: enqueueing, job state tracking,
worker execution, retries, dead-letter handling, and dashboard polling.

Deployment, production observability, stronger test coverage, and more complete
task output storage are still planned work.

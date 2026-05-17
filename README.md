# VortexQueue

A production-grade distributed task queue built from scratch in Python — no Celery, no abstractions. Demonstrates raw Redis primitives, crash recovery, distributed locking, idempotency, and graceful degradation.

**Stack:** FastAPI · PostgreSQL · Redis · Next.js

---

## Architecture

```
[Browser / Dashboard]
        │
        ▼ HTTP POST /api/jobs
[FastAPI API]  ──LPUSH──▶  [Redis: vortex:queue:main (List)]
        │                               │
        │ writes QUEUED                 │ BRPOP (blocking pop)
        ▼                               ▼
[PostgreSQL: jobs]            [Worker Process]
        ▲                         │          │
        │ updates state            │          └──▶ [HeartbeatThread]
        │                         │                 EXPIRE key every 10s
        └─────────────────────────┘
                                  │ on failure
                                  ▼
                       [Retry + Exponential Backoff]
                       10s → 30s → 60s → 120s → 300s
                                  │ after MAX_RETRIES
                                  ▼
                       [PostgreSQL: dead_letter_queue]

[Janitor Process] ── every 60s ──▶ scans PROCESSING jobs
                                   checks vortex:processing:{id} in Redis
                                   if key expired → worker crashed → re-enqueue
```

---

## Engineering Decisions

| Decision | Why |
|---|---|
| Raw Redis `BRPOP` instead of Celery | Demonstrates understanding of queue primitives, not library usage |
| Visibility timeout + heartbeat instead of delete-on-pop | If a worker crashes mid-job, the key expires and the janitor rescues it — no message loss |
| Separate Janitor process | Decoupled responsibility; survives worker restarts independently |
| Idempotency via Redis `SET NX` | O(1) check prevents double-execution in at-least-once delivery (critical for invoice generation) |
| SIGTERM handler in worker | Worker finishes current job and returns it to queue on exit — zero data loss on deploy or scale-down |
| Exponential backoff → DLQ | Prevents a poison-pill job from starving the queue; exhausted jobs land in a queryable Postgres table |
| PostgreSQL as source of truth | Redis is ephemeral; DB survives restarts and gives the janitor a durable view of in-flight jobs |
| Task results in JSONB | Processed images (base64 PNG), PDFs, and scraped data stored directly — no S3 needed for a portfolio demo; interview answer: production would use object storage + key in DB |
| JSONB payload column | Flexible schema across 3 task types without separate tables |

---

## Task Types

**`image_processing`** — downloads a real image from a URL (5MB cap), applies Pillow transformations (resize, grayscale, watermark), returns the processed image as a downloadable PNG.

**`web_scraping`** — fetches a real URL with `requests` + BeautifulSoup, extracts elements by CSS selector, returns structured scraped content. Handles timeouts and 4xx/5xx errors (triggers retries).

**`bulk_invoice`** — generates a real PDF invoice using ReportLab with customer ID, line items, and totals. Returns the PDF as a downloadable file. Idempotency prevents double-generation.

---

## Project Structure

```
VortexQueue/
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── src/
│       ├── api/
│       │   ├── main.py        FastAPI app, CORS, lifespan
│       │   ├── routes.py      POST /jobs, GET /jobs/{id}, GET /dashboard-stats
│       │   └── schemas.py     Pydantic models
│       ├── core/
│       │   ├── config.py      Typed settings from .env
│       │   ├── database.py    psycopg2 pool, all DB helpers, table bootstrap
│       │   └── redis.py       Shared connection pool
│       ├── worker/
│       │   ├── main.py        BRPOP loop + SIGTERM graceful shutdown
│       │   ├── executor.py    Idempotency → dispatch → retry/DLQ logic
│       │   ├── heartbeat.py   Daemon thread, refreshes Redis TTL every 10s
│       │   └── tasks.py       image_processing, web_scraping, bulk_invoice
│       └── janitor/
│           └── main.py        Orphan recovery, 60s scan loop
├── frontend/
│   ├── app/page.tsx           Single-page dashboard
│   ├── components/
│   │   ├── ControlBar.tsx     Spawn Job, Stress Test ×50
│   │   ├── MetricsGrid.tsx    Live stat cards
│   │   ├── ThroughputChart.tsx Recharts line chart
│   │   ├── JobBoard.tsx       Kanban with Framer Motion animations
│   │   ├── SubmitJobForm.tsx  Custom job submission with real inputs
│   │   └── JobResultModal.tsx Image preview, PDF download, scraping viewer
│   └── lib/api.ts             Typed fetch wrappers for all endpoints
├── docker-compose.yml
└── .env.example
```

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL running locally (database: `job_queue_db`)
- Redis running locally

---

## Setup

**Backend:**
```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows
pip install -r backend/requirements.txt
```

Copy and fill in credentials:
```bash
cp backend/.env.example backend/.env
```

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/job_queue_db
REDIS_URL=redis://localhost:6379/0
MAIN_QUEUE=vortex:queue:main
VISIBILITY_TIMEOUT=300
MAX_RETRIES=5
LOG_LEVEL=DEBUG
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.local.example .env.local
```

---

## Run Locally

Three terminals:

```bash
# Terminal 1 — API
cd backend
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Worker
cd backend
python -m src.worker.main

# Terminal 3 — Frontend
cd frontend
npm run dev
```

Open `http://localhost:3000`. API docs at `http://localhost:8000/docs`.

Optionally run the janitor in a fourth terminal:
```bash
cd backend && python -m src.janitor.main
```

---

## Demo Scenarios

**Basic flow:** Click "Spawn Job" → watch the card move Queued → Processing → Done on the Kanban board.

**Stress test:** Click "Stress Test ×50" → 50 mixed jobs fire concurrently. Queue Depth spikes, workers drain it.

**Custom job with real output:** Expand "Submit Custom Job" → pick Web Scraping → enter any URL → submit → click "View Result" to see live scraped data. Or submit an invoice and download the generated PDF.

**Retry + DLQ:** Submit a web scraping job with a broken URL. Watch the retry counter increment on the card across 5 attempts with exponential backoff (10s → 30s → 60s → 120s → 300s). After the 5th failure, the Dead Letter count goes red.

**Crash recovery (janitor demo):**
1. Set `VISIBILITY_TIMEOUT=30` in `backend/.env`, restart processes
2. Submit a job, kill the worker the moment it hits Processing
3. Start the janitor — it detects the expired Redis lock and re-enqueues the job
4. Restart the worker — job completes cleanly

---

## API

```
POST /api/jobs              Enqueue a job (202 Accepted)
GET  /api/jobs/{job_id}     Get job status + result
GET  /api/dashboard-stats   Live metrics for the dashboard
```

Task types: `image_processing` · `web_scraping` · `bulk_invoice`

---

## Docker

```bash
cp .env.example .env        # set POSTGRES_PASSWORD
docker compose up --build
docker compose up --scale worker=3  # horizontal worker scaling
```

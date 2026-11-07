# AURA-Traffic: CCTV Motorcycle Wrong-Way & Crosswalk Safety Analyzer

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![UV](https://img.shields.io/badge/UV-Package%20Manager-purple.svg)](https://docs.astral.sh/uv/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end computer vision and traffic safety monitoring system that analyzes intersection CCTV footage to detect and track motorcycles, classify riding vs. walking dismounted posture, and verify suspected safety violations (wrong-way travel and pedestrian crosswalk intrusions) across temporal sequences.

---

## 🏛️ Monorepo Architecture

The repository is structured as a modular polyglot monorepo:

```
CCTV-Safety/
│
├── backend/                        # ALL Python code & packaging (UV-managed)
│   ├── pyproject.toml              # UV dependencies, hatchling build & test configuration
│   ├── .env.example                # Configurable environment templates
│   ├── src/                        # Computer Vision & Safety Core Engine (<100 LOC/file)
│   │   ├── core/                   # Anchors, perspective scaling, kinematics, motion
│   │   ├── config/                 # Intersection zone models & loaders
│   │   ├── tracking/               # Detection, tracking manager, NMS gating, track states
│   │   ├── safety/                 # Direction analysis, lane clustering, crosswalk rules, fusion
│   │   ├── analytics/              # Temporal FSM verifier, explanation engine, evaluator
│   │   └── pipeline/               # Multi-stage batch & streaming processor
│   ├── app/                        # FastAPI REST Application (<100 LOC/file)
│   │   ├── main.py                 # FastAPI application factory, CORS, lifespan
│   │   ├── config.py               # Pydantic BaseSettings, dynamic root path resolution
│   │   ├── dependencies.py         # Dependency injection singletons
│   │   ├── schemas/                # Request & response Pydantic DTOs
│   │   ├── services/               # Video streaming, zones, events & pipeline execution
│   │   └── routers/                # REST API controllers (/health, /videos, /zones, /events, /pipeline)
│   ├── notebooks/                  # Experimental research notebooks
│   │   └── cctv_safety_pipeline.ipynb
│   └── tests/                      # Automated test suite (pytest)
│       ├── test_safety_rules.py    # Unit tests for kinematics and rules
│       ├── test_events_export.py   # Machine-readable JSON/CSV export tests
│       └── test_backend_api.py     # FastAPI TestClient integration tests
│
├── frontend/                       # [Planned] Next.js Dashboard UI (Node.js/TypeScript)
├── docker/                         # [Planned] Multi-stage container definitions & compose.yaml
│
├── configs/                        # Shared runtime configuration
│   └── zones.json                  # Calibrated intersection road polygon, crosswalks & lanes
├── data/                           # Shared runtime media & outputs
│   ├── videos/                     # Input CCTV MP4 recordings
│   ├── reference_frames/           # Camera calibration keyframes
│   └── output/                     # Analysis artifacts (detected_events.json, CSV, evidence cards)
├── models/                         # YOLO model weights (yolo11m.pt, yolov8s.pt)
│
├── .gitignore                      # Polyglot rules (Python, Node/Next.js, datasets)
└── README.md                       # Repository guide
```

---

## 🚀 Quickstart & Backend Execution

### 1. Requirements
- Python 3.10+
- `uv` (Fast Python package installer and resolver)

### 2. Setup with UV
From the `backend/` directory:
```bash
cd backend
uv venv
uv pip install -e .
```

### 3. Run the FastAPI Server
From within `backend/`:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Or from the monorepo root:
```bash
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 4. Run the Next.js Dashboard Frontend
From within `frontend/`:
```bash
cd frontend
pnpm install
pnpm dev
```
Open `http://localhost:3000` in your browser to access the interactive AURA-Traffic Safety Analyzer dashboard.

---

## 🧪 Running Automated Tests

Run the test suite using pytest:
```bash
cd backend
pytest tests/ -v
```

---

## 📡 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health, GPU/CPU accelerator status, and uptime |
| `GET` | `/api/videos` | Catalog of available CCTV recordings with metadata |
| `POST` | `/api/videos/upload` | Multipart file upload for new video footage |
| `GET` | `/api/videos/{name}/stream` | HTTP 206 partial-content video streaming |
| `GET` | `/api/config/zones` | Retrieve intersection road, crosswalk, and lane polygons |
| `PUT` | `/api/config/zones` | Update zone coordinates and direction vector arrows |
| `POST` | `/api/config/zones/reset` | Reset zones to initial calibrated reference coordinates |
| `GET` | `/api/events` | Filterable list of confirmed, exempt, and ignored events |
| `GET` | `/api/events/{event_id}` | Event detail, posture metrics, and alignment gauge |
| `GET` | `/api/events/{event_id}/frames/{type}` | Serve 3-frame evidence strip (entry, midpoint, exit) |
| `GET` | `/api/events/export/json` | Export detected events in machine-readable JSON |
| `GET` | `/api/events/export/csv` | Export detected events in machine-readable CSV |
| `POST` | `/api/pipeline/start` | Trigger asynchronous video analysis job |
| `GET` | `/api/pipeline/status/{task_id}` | Check job progress and elapsed time |
| `GET` | `/api/pipeline/telemetry` | Live Telemetry HUD pills (FPS, active tracks, latency) |

---

## 🛡️ Code Quality Standards
- **Strict File Limit**: Every Python file across `src/`, `app/`, and `tests/` is strictly under **100 lines of code**.
- **Zero Hardcoding**: All paths and parameters are dynamic and configurable via environment variables.
- **Stateless Deployment**: File-based persistence without requiring a database server.

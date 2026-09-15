# CongestiQ Backend

FastAPI-based backend for the CongestiQ port congestion prediction system.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or use the Docker Compose setup at the repo root)

## Setup

```bash
cd src/backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and set DATABASE_URL to your PostgreSQL connection string
```

## Running the development server

```bash
uvicorn main:app --reload --port 8000
```

API will be available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

## Project layout

```
backend/
├── main.py          ← FastAPI app entry point
├── config.py        ← Settings loaded from environment variables
├── requirements.txt
├── .env.example
├── db/              ← SQLAlchemy models and session (Phase 1)
├── routers/         ← API route handlers (Phase 1+)
└── services/        ← Business logic and prediction engines (Phase 2+)
```

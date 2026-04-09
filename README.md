# Kitchen API

FastAPI + PostgreSQL backend for the Kitchen platform. Manages restaurants, plate selection, subscriptions, billing, and multi-tenant institution scoping.

## Quick Start

```bash
# Clone and enter project
cd ~/learn/kitchen

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your SECRET_KEY, DB_* values, etc.

# Run database (PostgreSQL via Docker or local)
# See docs/database/ for schema setup
# app/db/build_kitchen_db.sh for dev rebuild

# Start API
uvicorn application:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## Documentation

Full documentation lives in [docs/](docs/):

- **[docs/README.md](docs/README.md)** — Documentation index
- **[CLAUDE.md](CLAUDE.md)** — Development principles and conventions
- **[CLAUDE_ARCHITECTURE.md](CLAUDE_ARCHITECTURE.md)** — Architecture overview
- **[docs/postman/](docs/postman/)** — Postman collections and testing
- **[docs/database/](docs/database/)** — Database schema and rebuild procedures

## Stack

- **FastAPI** — Web framework
- **PostgreSQL** — Database (psycopg2)
- **Pydantic** — Validation and settings
- **JWT** — Authentication

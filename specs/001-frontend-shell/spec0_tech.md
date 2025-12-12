## Backend

**Language & Runtime**

* Python (3.11+)

**Web API**

* FastAPI (ASGI framework)
* Uvicorn (ASGI server)

**Data Modeling & Config**

* Pydantic (v2) for:

  * Domain models (e.g. `Project`)
  * Request/response schemas
* pydantic-settings (or equivalent) for typed settings
* YAML (PyYAML) for environment/config files

**Persistence**

* Primary: MongoDB

  * Access via `motor` or an ODM like **Beanie**
* Optional local mode (config-driven):

  * Either local MongoDB container
  * Or simple JSON/SQLite-based storage for Projects

**Logging & Observability**

* Loguru for structured, ergonomic logging
* Prometheus Python client for metrics (e.g. `/metrics` endpoint)
* (Later) Grafana or similar for dashboards (optional)

---

## Frontend

**Core**

* React
* TypeScript
* Vite (bundler/dev server) – SPA-style app

**UI & Styling**

* Tailwind CSS
* (Optional but recommended) Headless component helpers:

  * Headless UI / Radix UI for primitives
  * Simple custom components for tabs, forms, modals

**State & Data Flow**

* React Context for shared `Project` object across tabs (Ground Zero)
* (Later) TanStack Query / React Query for syncing with backend APIs

---

## DevOps / Tooling

**Version Control & CI**

* GitHub + GitHub Actions for:

  * Linting & tests
  * Building Docker images

**Containerization & Env**

* Docker for backend, frontend, MongoDB
* docker-compose for local multi-service dev

**Developer Experience**

* Makefile for common tasks:

  * `make dev` (start stack)
  * `make test`
  * `make lint`
  * `make build`
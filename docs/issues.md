Here's the full operational plan: **29 issues** covering the entire backend roadmap from the audit. Same format as the frontend issues, ready to paste into GitHub.

Issue ID prefix: `BE-` (backend)

---

# 🗂️ REPO: `mayda-backend` — Phase 0: Repo Initialization

### ISSUE BE-001: Initialize `mayda-backend` repo from `API_Orchestration/`

**Description**
The folder is already a git repository with full history. Push it as the new `mayda-backend` repo under the `mayda` organization, update metadata, and add a proper README documenting the FastAPI + SQLAlchemy stack.

**Goal**
Repo exists on GitHub with the existing codebase + commit history intact.

**Targeted Files**
- All of `API_Orchestration/` (push as-is)
- `README.md` (overwrite)
- `.gitignore` (verify Python defaults)

**Tasks**
- [ ] Verify existing `.git/` is clean — `git status` in `API_Orchestration/`
- [ ] Create GitHub repo `mayda/mayda-backend` (public)
- [ ] `git remote add origin git@github.com:mayda/mayda-backend.git`
- [ ] `git push -u origin main`
- [ ] Rewrite `README.md` with stack, dev commands, env-var checklist
- [ ] Verify `.gitignore` excludes `__pycache__/`, `.env`, `*.pyc`, `alembic/versions/` if needed

**Acceptance Criteria**
- Repo accessible at `https://github.com/mayda/mayda-backend`
- `git clone && cp .env.example .env && pip install -r requirements.txt && alembic upgrade head` works
- README documents the dev startup sequence

**References**
- AUDIT.md → "Repository Overview"
- [API_Orchestration/](API_Orchestration/)

**Blocked By**
- None

---

# 🚨 Phase 1 — Critical Unblockers (BE-002, BE-003 in parallel)

### ISSUE BE-002: Register the 3 missing routers (`loyalty`, `ingredients`, `inventory`)

**Description**
Three route modules totaling **2,064 lines of code** exist but are never registered in `main.py`. Frontend issues CH-006, MG-009 already expect `/ingredients` and `/inventory` endpoints. This is a one-line fix per module that unlocks massive functionality.

**Goal**
All 14 route modules exposed via `/docs`; frontend can call the endpoints.

**Targeted Files**
- `main.py` (import + register)

**Tasks**
- [ ] Add imports: `from app.routes import loyalty, ingredients, inventory`
- [ ] Add registrations:
  ```python
  app.include_router(loyalty.router, prefix="/api")
  app.include_router(ingredients.router, prefix="/api")
  app.include_router(inventory.router, prefix="/api")
  ```
- [ ] Run server, verify all 3 routers appear in `/docs`
- [ ] Smoke-test each with `curl` against a known endpoint per router

**Acceptance Criteria**
- `/docs` shows 14 router tags (was 11)
- `GET /api/ingredients` returns 200 (or 401 if auth-gated — not 404)
- `GET /api/inventory` returns 200/401
- `GET /api/loyalty/...` returns 200/401

**References**
- AUDIT.md → "CRITICAL: Three unregistered routers"
- Current: [main.py:110-121](API_Orchestration/main.py)
- [loyalty.py](API_Orchestration/app/routes/loyalty.py), [ingredients.py](API_Orchestration/app/routes/ingredients.py), [inventory.py](API_Orchestration/app/routes/inventory.py)

**Blocked By**
- BE-001

---

### ISSUE BE-003: Migrate backend port from 8000 → 8001 across all configs

**Description**
The recommendation service expects to call back to the Gateway at `http://localhost:8001/api` ([recommendation .env.example](Recommendation_system_for_meals/recommendation-service/.env.example)), but the backend listens on 8000. Standardize on 8001 to match the architecture blueprint and downstream expectations.

**Goal**
Backend listens on 8001 in dev + Docker; healthcheck and downstream services agree on the port.

**Targeted Files**
- `main.py` (uvicorn port)
- `Dockerfile` (EXPOSE + HEALTHCHECK + CMD)
- `docker-compose.yml` (ports mapping)
- `nginx.conf` (upstream port)
- `README.md` (dev command)

**Tasks**
- [ ] `main.py:151` → change `port=8000` to `port=8001`
- [ ] `Dockerfile:49` → `EXPOSE 8001`
- [ ] `Dockerfile:53` → healthcheck URL → `http://localhost:8001/docs`
- [ ] `Dockerfile:56` → `--port 8001`
- [ ] `docker-compose.yml:31` → `"8001:8001"`
- [ ] `docker-compose.yml:58` → `--port 8001`
- [ ] `nginx.conf:7` → `server api:8001`
- [ ] Document new port in `README.md`

**Acceptance Criteria**
- `curl http://localhost:8001/health` returns 200 in dev and in Docker
- `docker compose up` exposes the API on 8001
- nginx successfully proxies to upstream
- Port 8000 no longer referenced anywhere

**References**
- AUDIT.md → "Port mismatch with downstream services"
- [recommendation-service/.env.example:7](Recommendation_system_for_meals/recommendation-service/.env.example)

**Blocked By**
- BE-001

---

# 🤖 Phase 2 — AI Proxy Layer

### ISSUE BE-004: Add AI service configuration + `httpx` + proxy infrastructure

**Description**
Foundation for all AI proxy routes. Adds env-var config for the 4 AI service URLs + shared service token, installs `httpx` for async HTTP, and creates a reusable proxy helper that handles token forwarding, request ID propagation, and error normalization.

**Goal**
A single `proxy_to_service()` helper that any `/ai/*` route can call in one line.

**Targeted Files**
- `requirements.txt` (add `httpx`)
- `app/core/config.py` (add 5 settings)
- `app/utils/ai_proxy.py` (new helper)
- `.env.example` (document new vars)

**Tasks**
- [ ] Add to `requirements.txt`: `httpx==0.27.0`
- [ ] Add 5 settings to `app/core/config.py`:
  ```python
  RECOMMENDATION_SERVICE_URL: str = "http://recommendation:8101"
  SEARCH_SERVICE_URL: str = "http://search-llm:8102"
  INVENTORY_SERVICE_URL: str = "http://inventory:8103"
  VOICE_SERVICE_URL: str = "http://voice-chef:8104"
  SERVICE_TOKEN: str = ""
  ```
- [ ] Create `app/utils/ai_proxy.py` exporting `async def proxy_to_service(base_url, path, *, method, json=None, files=None, request_id, timeout=15)` — uses `httpx.AsyncClient`, attaches `X-Service-Token` + `X-Request-Id`, raises `HTTPException` on non-2xx with upstream detail
- [ ] Document new env vars in `.env.example`

**Acceptance Criteria**
- `proxy_to_service` returns parsed JSON on 2xx
- Upstream 4xx/5xx surfaces as a matching `HTTPException`
- Timeout raises 504 Gateway Timeout
- `SERVICE_TOKEN` validated as non-empty at startup (fail-fast)

**References**
- AUDIT.md → "Zero `/ai/*` proxy endpoints"
- Architecture Foundation (composite architecture map)

**Blocked By**
- BE-001

---

### ISSUE BE-005: Add `POST /ai/recommend` proxy → recommendation service

**Description**
Thin proxy routing authenticated requests to `mayda-ai/recommendation`. Frontend feature `WC-007` calls this endpoint. Authenticated users only — strips PII, injects user ID.

**Goal**
Web-client's `useRecommendations()` query returns AI-powered recommendations.

**Targeted Files**
- `app/routes/ai.py` (new file, contains all `/ai/*` routes)
- `app/models/ai.py` (new — Pydantic shapes for proxy payloads)
- `main.py` (register router)

**Tasks**
- [ ] Create `app/routes/ai.py` with router prefix `/ai`, tag `["AI"]`
- [ ] Add `POST /recommend`: accepts `{cartItemIds, timeOfDay}`, depends on `get_current_user`, forwards `{user_id, cart_item_ids, time_of_day}` via `proxy_to_service`
- [ ] Define `RecommendRequest` + `RecommendResponse` Pydantic models in `app/models/ai.py`
- [ ] Register router in `main.py` with prefix `/api`
- [ ] Add docstring + OpenAPI tag

**Acceptance Criteria**
- `/docs` shows `POST /api/ai/recommend`
- Authenticated call returns AI service payload
- Missing token returns 401
- Recommendation service down returns 502/504, not 500

**References**
- Frontend issue WC-007
- AI service: [recommendation-service](Recommendation_system_for_meals/recommendation-service/)
- BE-004

**Blocked By**
- BE-004, mayda-ai/recommendation service exposes `POST /recommendations`

---

### ISSUE BE-006: Add `POST /ai/search` proxy → search-llm service

**Description**
Proxy for natural-language menu/dish search. Public endpoint (no auth required) since search is a discovery feature.

**Goal**
Mobile + web clients can search dishes via natural language.

**Targeted Files**
- `app/routes/ai.py` (append)
- `app/models/ai.py` (append)

**Tasks**
- [ ] Add `POST /search`: accepts `{query, restaurantId?, limit?}`, no auth dependency
- [ ] Forwards to `SEARCH_SERVICE_URL` via `proxy_to_service`
- [ ] Define `SearchRequest` + `SearchResponse` models
- [ ] Add rate limiting (5/min/IP) once BE-027 lands

**Acceptance Criteria**
- `/docs` shows `POST /api/ai/search`
- Anonymous request returns results
- Search service down → 504

**References**
- AI service: [search-llm/main.py](search-llm/main.py)
- BE-004

**Blocked By**
- BE-004, mayda-ai/search exposes `POST /search`

---

### ISSUE BE-007: Add `POST /ai/inventory/forecast` proxy → inventory service

**Description**
Proxy for AI-driven stock forecasting. Used by both chef (CH-006) and manager (MG-009) frontends. Staff-only.

**Goal**
Chef + manager dashboards display AI-forecasted ingredient needs.

**Targeted Files**
- `app/routes/ai.py` (append)
- `app/models/ai.py` (append)

**Tasks**
- [ ] Add `POST /inventory/forecast`: accepts `{item, date, weather?, specialEvent?}`, depends on `get_current_staff_user`
- [ ] Forwards to `INVENTORY_SERVICE_URL`
- [ ] Define `ForecastRequest` + `ForecastResponse` models

**Acceptance Criteria**
- Staff-only access enforced
- Forecast pulls live data through the proxy
- Inventory service down → 504, doesn't crash the route

**References**
- Frontend issues CH-006, MG-009
- AI service: [Inventory_prediction](Inventory_prediction/)

**Blocked By**
- BE-004, mayda-ai/inventory FastAPI shim exposes `POST /forecast`

---

### ISSUE BE-008: Add `POST /ai/voice/transcribe` proxy → voice-chef (multipart)

**Description**
**Multipart audio passthrough** to the Whisper service. More complex than the other proxies because `httpx` needs to forward the `UploadFile` as multipart, not JSON. Used by both chef (CH-008) and mobile (MB-009) voice features.

**Goal**
Audio recorded in any client → transcribed via Whisper.

**Targeted Files**
- `app/routes/ai.py` (append)
- `app/utils/ai_proxy.py` (add `proxy_multipart_to_service`)
- `app/models/ai.py` (append)

**Tasks**
- [ ] Add `proxy_multipart_to_service(base_url, path, *, audio_file, request_id)` helper in `ai_proxy.py` — uses `httpx`'s `files=` parameter
- [ ] Add `POST /voice/transcribe` route accepting `audio: UploadFile = File(...)`, depends on `get_current_user`
- [ ] Forward to `VOICE_SERVICE_URL`
- [ ] Define `TranscribeResponse` model
- [ ] Set `max_request_size` to 20MB in route to allow audio uploads

**Acceptance Criteria**
- 5-second .m4a upload returns transcript
- 30MB upload returns 413 Payload Too Large
- Voice service down → 504
- Multipart headers preserved through proxy

**References**
- Frontend issues CH-008, MB-009
- AI service: [Voice-Chef](Voice-Chef---AI-Voice-Interface-for-Restaurant-Orders/)

**Blocked By**
- BE-004, mayda-ai/voice FastAPI shim exposes `POST /transcribe`

---

### ISSUE BE-009: Add `/ai/anomalies` GET + ack endpoints

**Description**
Admin-only proxy endpoints for AI-flagged anomalies. The admin panel (AD-008) lists detected anomalies with severity and lets admin acknowledge them.

**Goal**
Admin reviews + dismisses AI-detected unusual activity.

**Targeted Files**
- `app/routes/ai.py` (append)
- `app/models/ai.py` (append)

**Tasks**
- [ ] Add `GET /anomalies?range=…`: admin-only via `get_current_admin_user`, proxies to anomaly-detection service
- [ ] Add `POST /anomalies/{id}/ack`: admin-only, forwards ack to upstream
- [ ] Define `Anomaly` + `AnomalyAckResponse` models
- [ ] **Decision needed:** which AI service owns anomalies? Could extend recommendation, or be a new sub-service. For hackathon, defer to mock backend response if service isn't built.

**Acceptance Criteria**
- Admin-only access enforced
- `/docs` shows both endpoints
- If anomaly service is mocked, returns sample list

**References**
- Frontend issue AD-008
- BE-004

**Blocked By**
- BE-004, anomaly service decision

---

# 🔒 Phase 3 — Security Hardening (parallelizable: BE-010, BE-011, BE-012)

### ISSUE BE-010: Remove default `SECRET_KEY` + enforce env-var presence

**Description**
The default JWT secret `"your-secret-key-change-this-in-production"` exists in both `config.py` AND `docker-compose.yml`. Anyone with the public repo can forge tokens. Make `SECRET_KEY` required (no default) so the app fails to start if missing.

**Goal**
Application refuses to start without a real `SECRET_KEY` set in the environment.

**Targeted Files**
- `app/core/config.py`
- `docker-compose.yml`
- `.env.example`
- `README.md`

**Tasks**
- [ ] `config.py`: remove default value — declare `SECRET_KEY: str` with no default (pydantic-settings will raise if missing)
- [ ] `docker-compose.yml:34`: remove `:-...` fallback → use `SECRET_KEY=${SECRET_KEY:?SECRET_KEY required}`
- [ ] `.env.example`: document with `SECRET_KEY=$(openssl rand -hex 32)` example command
- [ ] README: add section "Required env vars" listing all must-haves

**Acceptance Criteria**
- `python main.py` without `SECRET_KEY` raises `ValidationError` at startup
- `docker compose up` without `SECRET_KEY` exits with clear error
- README documents the required generation command

**References**
- AUDIT.md → "Default secret in two places"
- Current: [config.py:7](API_Orchestration/app/core/config.py), [docker-compose.yml:34](API_Orchestration/docker-compose.yml)

**Blocked By**
- BE-001

---

### ISSUE BE-011: Replace hardcoded CORS with env-driven regex

**Description**
CORS is currently locked to `localhost:3000` + `localhost:8080` — breaks all 5 Vercel-deployed frontends and every preview URL. Replace with a regex pattern reading from env.

**Goal**
All `mayda.app` subdomains + `*.vercel.app` preview URLs + localhost work without per-deploy reconfiguration.

**Targeted Files**
- `app/core/config.py`
- `main.py` (CORS middleware)
- `.env.example`

**Tasks**
- [ ] Add to `config.py`:
  ```python
  BACKEND_CORS_ORIGIN_REGEX: str = (
      r"https?://(localhost(:\d+)?|.*\.mayda\.app|.*\.vercel\.app)"
  )
  ```
- [ ] Remove or empty `BACKEND_CORS_ORIGINS`
- [ ] `main.py`: replace `allow_origins=settings.BACKEND_CORS_ORIGINS` with `allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX`
- [ ] Document in `.env.example`

**Acceptance Criteria**
- `OPTIONS` preflight from `https://mayda.app` returns `Access-Control-Allow-Origin: https://mayda.app`
- Preflight from `https://random-pr-123.vercel.app` succeeds
- Preflight from `https://attacker.com` fails

**References**
- AUDIT.md → "CORS hardcoded to two origins"
- Current: [config.py:25](API_Orchestration/app/core/config.py)

**Blocked By**
- BE-001

---

### ISSUE BE-012: Add request ID middleware for tracing

**Description**
Generate a UUID per request, attach to `request.state.request_id`, include in `X-Request-Id` response header, and propagate to all AI proxy calls (via `proxy_to_service`). Enables end-to-end tracing across the gateway + AI services.

**Goal**
Every request has a traceable ID surfaced in logs + downstream calls.

**Targeted Files**
- `app/middleware/request_id.py` (new)
- `main.py` (register middleware)
- `app/utils/ai_proxy.py` (read from request state)

**Tasks**
- [ ] Create `app/middleware/request_id.py` with `RequestIdMiddleware` (ASGI-style)
- [ ] Honors incoming `X-Request-Id` if present, else generates UUID4
- [ ] Sets `request.state.request_id`
- [ ] Returns `X-Request-Id` in response
- [ ] Register in `main.py` (before CORS)
- [ ] Update `proxy_to_service` to read from `request.state` (route handlers pass `request` in)

**Acceptance Criteria**
- Every response has `X-Request-Id` header
- Client-provided `X-Request-Id` is preserved (echoed back)
- AI service receives same `X-Request-Id` from proxy

**References**
- AUDIT.md → "No request ID propagation"

**Blocked By**
- BE-001 (BE-004 must merge before AI proxy can use it)

---

# 🔧 Phase 4 — Modernization (sequential: BE-013 → BE-014 → BE-015)

### ISSUE BE-013: Migrate `@app.on_event` to `lifespan` context manager

**Description**
`@app.on_event("startup")` and `("shutdown")` are deprecated in FastAPI 0.110+. Migrate to the `lifespan` async context manager pattern (single function, yields once between startup and shutdown).

**Goal**
No deprecation warnings on startup; cleaner pattern.

**Targeted Files**
- `main.py`

**Tasks**
- [ ] Define `@asynccontextmanager async def lifespan(app: FastAPI)`
- [ ] Before `yield`: call `connect_db()` + `ensure_admin_user_exists()`
- [ ] After `yield`: call `disconnect_db()`
- [ ] Pass `lifespan=lifespan` into `FastAPI(...)` constructor
- [ ] Remove the two `@app.on_event` decorators

**Acceptance Criteria**
- App starts and stops cleanly
- No deprecation warnings in logs
- `connect_db` runs before any request

**References**
- AUDIT.md → "Deprecated FastAPI startup pattern"
- Current: [main.py:48, 100](API_Orchestration/main.py)
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/)

**Blocked By**
- BE-001

---

### ISSUE BE-014: Convert `get_db()` to FastAPI dependency

**Description**
115 routes currently call `db = get_db()` directly — a global singleton lookup. Convert to a FastAPI dependency \`db = Depends(get_db_session)\` so we can test with overrides + scope sessions per request later.

**Goal**
Routes receive their DB client as a dependency, not via global lookup.

**Targeted Files**
- `app/core/database.py` (add `get_db_session` generator)
- All 14 files in `app/routes/` (~115 line changes — automatable with `sed`)

**Tasks**
- [ ] Add to `database.py`:
  ```python
  async def get_db_session():
      yield get_db()
  ```
- [ ] Run `sed` or codemod across all routes to:
  - Add `from app.core.database import get_db_session` (replacing `get_db`)
  - In each function signature, add `db = Depends(get_db_session)`
  - Remove the `db = get_db()` line from function body
- [ ] Manual review: spot-check 3 routes to confirm transformation is correct
- [ ] Run full smoke test of `/docs` after migration

**Acceptance Criteria**
- `grep -rn "get_db()" app/routes/` returns zero hits
- All routes have `db = Depends(get_db_session)` in their signature
- All endpoints still work (verify with seed script)
- Easier to mock DB in tests (verify with one example test)

**References**
- AUDIT.md → "Global DB singleton"
- Current: 115 occurrences across [app/routes/](API_Orchestration/app/routes/)

**Blocked By**
- BE-013

---

### ISSUE BE-015: Move hardcoded admin seed out of startup into a CLI command

**Description**
`ensure_admin_user_exists()` in `main.py` auto-creates `admin@caravane.com / admin123456` on every startup. Move to a CLI command (`python -m app.cli create-admin`) so it doesn't run unconditionally in production.

**Goal**
Admin user creation is explicit, not implicit.

**Targeted Files**
- `app/cli/__init__.py` (new)
- `app/cli/create_admin.py` (new — wraps existing `create_admin.py` logic)
- `main.py` (remove `ensure_admin_user_exists` call from lifespan)
- `create_admin.py` (delete or re-export from CLI)
- `README.md` (document new command)

**Tasks**
- [ ] Create `app/cli/` package
- [ ] Move admin creation logic from `main.py:60-92` + top-level `create_admin.py` into `app/cli/create_admin.py`
- [ ] Add CLI entry: `python -m app.cli create-admin --email ... --password ...`
- [ ] Remove `ensure_admin_user_exists()` call from `lifespan` in `main.py`
- [ ] Document command in README

**Acceptance Criteria**
- Fresh container starts without auto-creating admin
- `python -m app.cli create-admin` (with required args) creates the user
- Command refuses to overwrite existing admin
- README has a "First-time setup" section

**References**
- AUDIT.md → "Hardcoded admin seed runs on every startup"
- Current: [main.py:60-92](API_Orchestration/main.py), [create_admin.py](API_Orchestration/create_admin.py)

**Blocked By**
- BE-013, BE-014

---

# 📋 Phase 5 — Missing Endpoints (all parallelizable after BE-014)

### ISSUE BE-016: Add analytics endpoints — `/analytics/restaurant` + `/analytics/kitchen`

**Description**
Two analytics endpoints driving the manager (MG-005) and chef (CH-007) dashboards. Aggregations over Orders/OrderItems with date-range filtering.

**Goal**
Manager + chef dashboards show live KPIs.

**Targeted Files**
- `app/routes/analytics.py` (new)
- `app/models/analytics.py` (new)
- `main.py` (register router)

**Tasks**
- [ ] Create `analytics.py` router with prefix `/analytics`, tag `["Analytics"]`
- [ ] Add `GET /restaurant?range=day|week|month`: manager-only, returns `{revenue, orderCount, avgOrderValue, topDishes, hourlyHeatmap}`
- [ ] Add `GET /kitchen?range=…`: staff-only, returns `{avgPrepMinutes, ordersPerHour, lateOrderRate}`
- [ ] Pydantic models for both responses
- [ ] Use SQLAlchemy aggregations + raw queries where needed
- [ ] Register in `main.py`

**Acceptance Criteria**
- Both endpoints return valid data against seed DB
- Range filter affects results
- Role gates enforced

**References**
- Frontend issues MG-005, CH-007
- Existing model: [Order model](API_Orchestration/app/models/sqlalchemy_models.py)

**Blocked By**
- BE-014

---

### ISSUE BE-017: Add admin endpoints — `/admin/stats`, `/admin/analytics`, `/admin/settings`

**Description**
Platform-wide aggregate endpoints for `mayda-admin`. Stats = real-time totals; analytics = time-windowed cross-restaurant metrics; settings = org-level config CRUD.

**Goal**
Super-admin dashboard, analytics, and settings pages all wire-ready.

**Targeted Files**
- `app/routes/admin.py` (new)
- `app/models/admin.py` (new)
- \`app/models/sqlalchemy_models.py\` (add \`PlatformSettings\` model)
- `main.py` (register router)

**Tasks**
- [ ] Create SQLAlchemy model in \`app/models/sqlalchemy_models.py\`:
  \`\`\`python
  class PlatformSettings(Base):
      __tablename__ = "platform_settings"

      id = Column(Integer, primary_key=True, default=1)
      currency = Column(String, default="USD")
      timezone = Column(String, default="UTC")
      default_operating_hours = Column(JSON)
      feature_flags = Column(JSON, default={})
      updated_at = Column(DateTime, onupdate=datetime.utcnow)
  \`\`\`
- [ ] \`alembic revision --autogenerate -m "add_platform_settings"\`
- [ ] `GET /stats`: admin-only, returns `{totalRestaurants, totalOrdersToday, revenueToday, activeUsers, recentActivity}`
- [ ] `GET /analytics?range=…`: admin-only, cross-restaurant aggregates
- [ ] `GET /settings`, `PUT /settings`: admin-only, single-row CRUD
- [ ] Register router

**Acceptance Criteria**
- All 3 endpoint groups respond correctly
- Settings persist + retrieve
- Admin role enforced

**References**
- Frontend issues AD-005, AD-007, AD-009

**Blocked By**
- BE-014

---

### ISSUE BE-018: Add staff CRUD nested under `/restaurants/{id}/staff`

**Description**
Manager's employees feature (MG-006) needs full CRUD for restaurant staff. Existing `/auth/register` creates users — but staff management needs list/update/remove scoped to a restaurant.

**Goal**
Manager can add/edit/remove staff for their own restaurant; admin can do it for any.

**Targeted Files**
- `app/routes/staff.py` (new) OR append to `restaurants.py`
- `app/models/staff.py` (new)

**Tasks**
- [ ] Create router with prefix `/restaurants/{restaurant_id}/staff`
- [ ] `GET /`: list staff (manager+ scoped to own restaurant, admin scoped to any)
- [ ] `POST /invite`: create staff user + send invite SMS via existing SMS service
- [ ] `PATCH /{user_id}`: update role/active status
- [ ] `DELETE /{user_id}`: soft-delete (set `isActive=false`)
- [ ] Reuse existing `require_restaurant_staff` middleware for ownership check

**Acceptance Criteria**
- Manager sees only own restaurant's staff
- Cross-restaurant access denied (403)
- Invite triggers SMS

**References**
- Frontend issue MG-006

**Blocked By**
- BE-014

---

### ISSUE BE-019: Add notifications endpoints — `GET /notifications`, `PATCH /notifications/{id}/read`

**Description**
In-app notification feed for manager (MG-010) and admin. Requires a new `Notification` model.

**Goal**
Users have a notification inbox driven by backend events.

**Targeted Files**
- \`app/models/sqlalchemy_models.py\` (add \`Notification\` model)
- \`app/routes/notifications.py\` (new)
- `app/models/notification.py` (new)
- Existing routes that should emit notifications (`orders.py`, `reservations.py`)

**Tasks**
- [ ] Add SQLAlchemy model:
  \`\`\`python
  class Notification(Base):
      __tablename__ = "notifications"

      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
      type = Column(String, nullable=False)
      title = Column(String, nullable=False)
      body = Column(String, nullable=False)
      metadata_ = Column("metadata", JSON, nullable=True)
      is_read = Column(Boolean, default=False)
      created_at = Column(DateTime, default=datetime.utcnow)

      user = relationship("User", back_populates="notifications")
      __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)
  \`\`\`
- [ ] Run migration
- [ ] `GET /notifications?unreadOnly=…`: returns user's notifications
- [ ] `PATCH /notifications/{id}/read`: marks one read
- [ ] `POST /notifications/read-all`: marks all read
- [ ] Hook order creation in `orders.py` to write a notification for restaurant staff
- [ ] Hook reservation creation similarly

**Acceptance Criteria**
- New order → manager sees notification within next poll
- Mark-as-read persists
- Unread count query is fast (uses index)

**References**
- Frontend issue MG-010, AD-005 (recent activity feed)

**Blocked By**
- BE-014

---

### ISSUE BE-020: Add `POST /tables/{id}/checkin` endpoint

**Description**
Waiter's QR scanner (WT-005) calls this on scan. Marks table as occupied + (optionally) creates a session record linking waiter to table.

**Goal**
QR scan = single API call that opens a table session.

**Targeted Files**
- `app/routes/tables.py` (append)
- `app/models/table.py` (append)

**Tasks**
- [ ] Add `POST /{table_id}/checkin`: waiter+ role required
- [ ] Validates table belongs to waiter's restaurant
- [ ] Updates table status (add `status` field to Table model if not present)
- [ ] Returns `{tableId, status, sessionId?}`
- [ ] If using session model, create `TableSession` row

**Acceptance Criteria**
- Valid checkin returns 200 + updated table
- Cross-restaurant checkin returns 403
- Already-occupied table returns 409 with current occupant info

**References**
- Frontend issue WT-005
- Current: [tables.py](API_Orchestration/app/routes/tables.py)

**Blocked By**
- BE-014

---

### ISSUE BE-021: Add `POST /users/me/push-token` endpoint

**Description**
Mobile app (MB-010) registers Expo push tokens. Need a model to store and a route to upsert.

**Goal**
Mobile clients register their push token; backend can send notifications later.

**Targeted Files**
- \`app/models/sqlalchemy_models.py\` (add \`PushToken\` model)
- `app/routes/auth.py` (append) OR new `app/routes/users.py`
- `app/models/user.py` (append)

**Tasks**
- [ ] Add SQLAlchemy model:
  \`\`\`python
  class PushToken(Base):
      __tablename__ = "push_tokens"

      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
      token = Column(String, unique=True, nullable=False)
      platform = Column(String, nullable=False)
      created_at = Column(DateTime, default=datetime.utcnow)

      user = relationship("User", back_populates="push_tokens")
  \`\`\`
- [ ] Run migration
- [ ] `POST /users/me/push-token`: authed, upserts token (delete-then-insert if token exists for another user)
- [ ] `DELETE /users/me/push-token/{token}`: removes on logout

**Acceptance Criteria**
- Token registration is idempotent
- Same token can't be associated with two users (transfers cleanly)
- Logout removes token

**References**
- Frontend issue MB-010

**Blocked By**
- BE-014

---

# 🧹 Phase 6 — Cleanup (BE-022 → BE-023 sequential; BE-024, BE-025 parallel)

### ISSUE BE-022: Switch auth to non-debug SMS service + verify flow

**Description**
`routes/auth.py:12` imports the DEBUG SMS service (`sms_service_debug.py`), which prints emoji-tagged debug output. The proper `sms_service.py` exists but is unused. Switch the import and verify the 2FA flow still works.

**Goal**
Production-grade SMS service in active import path.

**Targeted Files**
- `app/routes/auth.py:12`
- `app/utils/sms_service.py` (verify completeness vs. debug version)

**Tasks**
- [ ] Diff `sms_service.py` vs `sms_service_debug.py` to identify functional differences
- [ ] Port any missing logic from debug → service (preserving the same public API)
- [ ] Change `auth.py:12` from `sms_service_debug import SMSService` → `sms_service import SMSService`
- [ ] Run end-to-end staff login + OTP verify flow
- [ ] Verify no `print()` statements left from debug version

**Acceptance Criteria**
- Staff login still sends OTP
- OTP verification still succeeds
- No `[DEBUG]` prints in logs

**References**
- AUDIT.md → "Auth depends on DEBUG SMS service"
- Current: [routes/auth.py:12](API_Orchestration/app/routes/auth.py)

**Blocked By**
- BE-001

---

### ISSUE BE-023: Consolidate 3 SMS files into 1

**Description**
Three SMS modules exist: `sms_sender.py`, `sms_service.py`, `sms_service_debug.py`. After BE-022, debug is unused. Delete duplicates and keep one source of truth.

**Goal**
Single `app/utils/sms.py` (or `sms_service.py`) — no duplicates.

**Targeted Files**
- `app/utils/sms_service.py` (kept)
- `app/utils/sms_sender.py` (review then likely delete)
- `app/utils/sms_service_debug.py` (delete)

**Tasks**
- [ ] `grep -rn "sms_sender\|sms_service_debug" app/` — confirm no other importers
- [ ] Delete `sms_service_debug.py`
- [ ] Audit `sms_sender.py`: if its logic is a subset of `sms_service.py`, delete it; otherwise merge into `sms_service.py`
- [ ] Verify nothing breaks: full app smoke test

**Acceptance Criteria**
- Only one SMS module exists
- All imports resolved
- Smoke test passes

**References**
- AUDIT.md → "Three SMS implementations"

**Blocked By**
- BE-022

---

### ISSUE BE-024: Delete decorator-based RBAC; keep only FastAPI dependencies

**Description**
`middleware/roles.py` has both class-method decorators (fragile arg-introspection) AND FastAPI dependencies. Routes use the dependencies. The decorators are dead code that confuses readers.

**Goal**
Single RBAC pattern (FastAPI `Depends`).

**Targeted Files**
- `app/middleware/roles.py` (delete `RoleMiddleware` class + bottom `role_middleware` instance)

**Tasks**
- [ ] Verify no production code uses the decorators: `grep -rn "require_roles\|require_staff\|require_admin\|require_manager_or_admin\|role_middleware" app/routes`
- [ ] Delete `RoleMiddleware` class entirely (lines 8-107)
- [ ] Delete the `role_middleware = RoleMiddleware()` instance at the bottom
- [ ] Keep only the FastAPI dependency functions (lines 111-149)
- [ ] Update `CONTRIBUTING.md` or `README.md` with the canonical RBAC pattern

**Acceptance Criteria**
- `grep` confirms no usages of removed symbols
- App still runs; all RBAC tests pass
- File shrinks by ~100 lines

**References**
- AUDIT.md → "Inconsistent RBAC pattern"
- Current: [middleware/roles.py](API_Orchestration/app/middleware/roles.py)

**Blocked By**
- BE-001

---

### ISSUE BE-025: Fix JWT subject typing + `datetime.utcnow()` deprecation

**Description**
JWT `sub` is inconsistently typed (`int` vs `str` across functions). Also `datetime.utcnow()` is deprecated in Python 3.12. Standardize on `str` subject + timezone-aware UTC datetimes.

**Goal**
No deprecation warnings; consistent JWT subject handling.

**Targeted Files**
- `app/auth/jwt.py`
- `app/middleware/auth.py` (uses `int(user_id)`)

**Tasks**
- [ ] Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)` in `jwt.py`
- [ ] In `create_access_token` + `create_refresh_token`: ensure callers pass `{"sub": str(user_id)}`
- [ ] In `get_user_id_from_token`: cast `.get("sub")` to `int` at the boundary, return `int | None`
- [ ] Update callers in `auth.py` route + `middleware/auth.py:29` to remove redundant casts

**Acceptance Criteria**
- No `DeprecationWarning` on test runs
- All JWT operations work end-to-end
- `sub` is always `str` in payload, always `int` in app code

**References**
- AUDIT.md → "JWT uses datetime.utcnow()", "Subject type inconsistency in tokens"
- Current: [auth/jwt.py](API_Orchestration/app/auth/jwt.py)

**Blocked By**
- BE-001

---

# ✨ Phase 7 — Quality (BE-026, BE-027, BE-028 parallelizable)

### ISSUE BE-026: Add structured logging with `loguru` (replace all 55 `print()` calls)

**Description**
55 `print()` statements across the codebase. Replace with `loguru` for structured, leveled, file-friendly logging. Hook into FastAPI request lifecycle to log every request with the `X-Request-Id` (after BE-012).

**Goal**
Production-grade logging; no `print()` calls.

**Targeted Files**
- `requirements.txt`
- `app/utils/logging.py` (new)
- `main.py` (initialize logger, add request-log middleware)
- All files containing `print()` (~10 files based on audit)

**Tasks**
- [ ] Add to `requirements.txt`: `loguru==0.7.2`
- [ ] Create `app/utils/logging.py` with configured logger (JSON in prod, pretty in dev)
- [ ] Replace `print(...)` with `logger.info(...)` / `logger.error(...)` everywhere
- [ ] Add request-log middleware: log method + path + status + request_id + duration_ms
- [ ] Verify no `print()` remains: `grep -rn "^[[:space:]]*print(" app/ main.py create_admin.py`

**Acceptance Criteria**
- Logs are structured (JSON in prod) with request_id field
- `grep` returns no `print()` calls in app code
- Each request logs once with full metadata

**References**
- AUDIT.md → "55 print() statements"
- [loguru docs](https://loguru.readthedocs.io/)

**Blocked By**
- BE-012

---

### ISSUE BE-027: Add rate limiting with `slowapi`

**Description**
Public endpoints (`POST /orders/public`, `POST /auth/register`, `POST /auth/login`, `POST /ai/search`) are unprotected. Add `slowapi` for IP-based rate limiting.

**Goal**
Public endpoints rate-limited; no DoS surface.

**Targeted Files**
- `requirements.txt`
- `main.py` (register limiter)
- `app/routes/orders.py` (public route)
- `app/routes/auth.py` (login, register)
- `app/routes/ai.py` (search)

**Tasks**
- [ ] Add to `requirements.txt`: `slowapi==0.1.9`
- [ ] In `main.py`: initialize `Limiter(key_func=get_remote_address)` + register with app state
- [ ] Add `@limiter.limit("10/minute")` to `POST /orders/public`
- [ ] Add `@limiter.limit("5/minute")` to `POST /auth/register`, `POST /auth/login`
- [ ] Add `@limiter.limit("20/minute")` to `POST /ai/search`
- [ ] Configure 429 response with helpful detail

**Acceptance Criteria**
- 11th `POST /orders/public` in a minute returns 429
- Authenticated routes are not rate-limited (only public)
- 429 response includes `Retry-After` header

**References**
- AUDIT.md → "No rate limiting"

**Blocked By**
- BE-014

---

### ISSUE BE-028: Set up `pytest` + smoke tests for critical paths

**Description**
Zero tests exist. Add `pytest` + `pytest-asyncio` + `httpx`'s `AsyncClient`, write conftest that spins up the app with a test DB, and add smoke tests covering: auth, public order, ingredients (formerly dark), AI proxy.

**Goal**
Run `pytest` and get a green bar across the 8 most-critical endpoints.

**Targeted Files**
- `requirements-dev.txt` (new)
- `tests/conftest.py` (new)
- `tests/test_auth.py`, `tests/test_orders.py`, `tests/test_ingredients.py`, `tests/test_ai_proxies.py`
- `pyproject.toml` or `pytest.ini`

**Tasks**
- [ ] Create `requirements-dev.txt`: `pytest`, `pytest-asyncio`, `httpx`, `respx` (for mocking AI services)
- [ ] `conftest.py`: fixture creating async test client + DB override
- [ ] Write smoke tests:
  - `test_register_login` (auth flow)
  - `test_public_order_dine_in_only` (security boundary)
  - `test_list_ingredients` (proves BE-002 worked)
  - `test_ai_recommend_proxy_success` + `test_ai_recommend_proxy_upstream_down`
- [ ] Add CI workflow `.github/workflows/test.yml` running tests

**Acceptance Criteria**
- `pytest` runs locally, all tests pass
- CI workflow runs on every PR
- AI proxy tests mock upstream (no network)

**References**
- AUDIT.md → "Zero tests"

**Blocked By**
- BE-002, BE-005, BE-014

---

# 🐳 Phase 8 — Infrastructure

### ISSUE BE-029: Simplify Dockerfile to single-stage slim build

**Description**
The Dockerfile previously included a multi-stage build with Node.js for ORM client generation. Since the migration to SQLAlchemy, a single-stage Python slim build is sufficient.

**Goal**
Clean, slim Docker image with a single Python stage.

**Targeted Files**
- `Dockerfile`

**Tasks**
- [ ] Verify Dockerfile uses \`python:3.12-slim\` base image
- [ ] Ensure \`pip install -r requirements.txt\` is the only build step
- [ ] Verify image builds and app starts correctly

**Acceptance Criteria**
- \`docker build\` succeeds without Node.js
- Image starts and serves requests
- Database queries work in container

**References**
- AUDIT.md → "Dockerfile bloated by Node.js for ORM CLI"
- Current: [Dockerfile](API_Orchestration/Dockerfile)

**Blocked By**
- BE-003 (port migration must be in)

---

## 📊 Summary

| Phase | Issues | Hours | Critical Path? |
|---|---|---|---|
| 0 — Init | 1 (BE-001) | 0.25 | yes |
| 1 — Critical unblockers | 2 (BE-002, BE-003) | 0.5 | **yes** |
| 2 — AI proxy layer | 6 (BE-004 → BE-009) | 3 | yes |
| 3 — Security hardening | 3 (BE-010 → BE-012) | 1 | yes |
| 4 — Modernization | 3 (BE-013 → BE-015) | 2 | partial |
| 5 — Missing endpoints | 6 (BE-016 → BE-021) | 4 | parallelize |
| 6 — Cleanup | 4 (BE-022 → BE-025) | 2 | partial |
| 7 — Quality | 3 (BE-026 → BE-028) | 4 | optional |
| 8 — Infrastructure | 1 (BE-029) | 1 | optional |
| **TOTAL** | **29 issues** | **~18 hours** | |

**Critical 48h path:** BE-001 → BE-002 + BE-003 (parallel) → BE-004 → BE-005…BE-009 (parallel) → BE-010, BE-011, BE-012 (parallel) → BE-013 → BE-014 → BE-016, BE-018, BE-019, BE-020, BE-021 (parallel) → BE-024, BE-025 → BE-029. ~12 hours of focused work if 3-4 devs run parallel tracks.

**Defer to post-hackathon:** BE-026 (logging), BE-027 (rate limiting), BE-028 (tests), BE-015 (admin CLI cleanup), BE-023 (SMS consolidation).


# Vue Element Plus Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python-rendered local admin pages with a Vue 3 + Element Plus single-page app while keeping the existing local service, SQLite data, extension API, and Windows packaging flow.

**Architecture:** The Python service remains the API and static-file host. The new `frontend/` app builds to `frontend/dist`, and `local_service.py` serves the SPA for dashboard routes while keeping existing JSON endpoints available.

**Tech Stack:** Vue 3, Vite, Element Plus, Vue Router, Python `http.server`, SQLite.

---

### Task 1: Scaffold Frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/*`

- [ ] Create the Vue app with routes for dashboard, jobs, job detail, skills, projects, interviews, and settings.
- [ ] Add API helper functions that call existing local-service endpoints.
- [ ] Build a shared shell with left navigation and Element Plus layout.

### Task 2: API and Static Host

**Files:**
- Modify: `src/boss_job_assistant/local_service.py`
- Modify: `tests/test_local_service.py`

- [ ] Add `/api/*` aliases for existing JSON endpoints.
- [ ] Add `/api/jobs/detail`, `/api/jobs/status`, `/api/skills/detail`.
- [ ] Serve `frontend/dist/index.html` for browser routes.
- [ ] Keep old `/jobs/save` and extension endpoints compatible.

### Task 3: Package Integration

**Files:**
- Modify: `scripts/package_windows.bat`
- Modify: `src/boss_job_assistant/desktop_launcher.py`
- Modify: `tests/test_desktop_launcher.py`

- [ ] Build frontend before PyInstaller packaging.
- [ ] Bundle `frontend/dist` into the exe.
- [ ] Extract static frontend assets for local exe runs.

### Task 4: Verification and Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/development.md`
- Modify: `docs/packaging.md`

- [ ] Document frontend development and build commands.
- [ ] Run Python tests, extension tests, and frontend build.
- [ ] Commit and push.

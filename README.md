# SmartDeviceAI

Full-stack SmartDeviceAI application with React (Vite), FastAPI, Motor, MongoDB, and startup-loaded ML.

## Runtime contract (important)

SmartDeviceAI uses three local services in development:

- Frontend (Vite): `http://localhost:5173`
- Dashboard/Auth API: `http://127.0.0.1:8000` (`backend/app/main.py`)
- AI Inference API (YOLO + VLM): `http://127.0.0.1:5000` (`backend/app.py`)

Do **not** run `uvicorn app:app` from `backend`; that conflicts with the `backend/app/` package.

Use:

- `uvicorn app.main:app --reload --port 8000` for dashboard/auth API
- `python app.py` for AI inference API

## One-command startup (Windows PowerShell)

```powershell
.\start_smartdeviceai.ps1
```

This starts both backends + frontend, waits for health checks, and opens the frontend in your browser.

## Frontend (manual)

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Dashboard/Auth backend (manual)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## AI inference backend (manual)

This backend hosts YOLO + VLM endpoints (`/detect`, `/explain`, `/analyze`, `/analyze-batch`).

Files:

- `backend/app.py`
- `backend/app/routes/ai_inference.py`
- `backend/services/ai_service.py`
- `backend/database/sqlite_store.py`
- `backend/yolo_model.py`
- `backend/vlm_analysis.py`
- `backend/pricing.py`
- `backend/utils.py`

Run it locally:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Analyze endpoint:

```bash
POST http://127.0.0.1:5000/analyze
```

Form fields:

- `device_type`
- `model`
- `condition`
- `age`
- `images` (2 to 4 files)

## Environment

- Backend defaults expect local MongoDB at `mongodb://127.0.0.1:27017`
- Copy `backend/.env.example` to `backend/.env` to override defaults
- Copy `frontend/.env.example` to `frontend/.env` for custom backend targets (used by Vite proxy in dev)
- Set `OPENAI_API_KEY` before using the Flask VLM analysis route

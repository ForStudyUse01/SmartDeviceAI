# SmartDeviceAI

Full-stack SmartDeviceAI application with React (Vite), FastAPI, Motor, MongoDB, and startup-loaded ML.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Flask Valuation API

This repo also includes a modular Flask analysis backend for YOLO + VLM pricing flow.

Files:

- `backend/app.py`
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
- Copy `frontend/.env.example` to `frontend/.env` if you need a custom API URL
- Set `OPENAI_API_KEY` before using the Flask VLM analysis route

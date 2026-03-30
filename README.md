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

## Environment

- Backend defaults expect local MongoDB at `mongodb://127.0.0.1:27017`
- Copy `backend/.env.example` to `backend/.env` to override defaults
- Copy `frontend/.env.example` to `frontend/.env` if you need a custom API URL

# SmartDeviceAI Connectivity Validation Checklist

Use this checklist after any frontend/backend networking changes.

## 1) Start services

- Frontend: `http://localhost:5173`
- Dashboard/Auth API: `http://127.0.0.1:8000`
- AI API: `http://127.0.0.1:5000`

Recommended:

```powershell
.\start_smartdeviceai.ps1
```

## 2) Health checks

- `GET http://127.0.0.1:8000/health` -> `200` with `{"status":"ok"}`
- `GET http://127.0.0.1:5000/health` -> `200`
- `GET http://127.0.0.1:5000/health/full` -> includes:
  - `cuda_available`
  - `device`
  - `yolo_model_path`

## 3) Frontend proxy checks

- `GET http://127.0.0.1:5173/api/health` -> `200`
- `GET http://127.0.0.1:5173/ai/health/full` -> `200`

These validate Vite proxy routes for `/api` and `/ai`.

## 4) CORS checks

Test origins:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://192.168.1.10:5173` (LAN dev)

Expected: `Access-Control-Allow-Origin` matches each allowed origin for both `:8000` and `:5000`.

## 5) AI endpoint checks

Using a sample image:

- `POST http://127.0.0.1:5000/detect?conf_threshold=0.25` -> boxes + labels
- `POST http://127.0.0.1:5000/explain?conf_threshold=0.25` -> caption + description

Expected:

- at least one detection on known sample image
- human-readable explanation in response

## 6) UI behavior checks

- Login/signup calls succeed (dashboard API, port 8000).
- Scan/Hybrid pages no longer show generic `Failed to fetch`.
- If AI service is down, UI shows explicit AI backend message.
- If dashboard service is down, UI shows explicit dashboard backend message.

## 7) Persistence checks

- Ensure `database/smartdeviceai.db` exists.
- Verify `inference_logs` receives rows after `/detect` and `/explain` calls.


# SmartDeviceAI

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react&logoColor=black)
![YOLO](https://img.shields.io/badge/YOLO-Detection-7D3C98)
![Status](https://img.shields.io/badge/Status-Project%20Ready-success)

SmartDeviceAI is an end-to-end AI-powered device analysis platform for e-waste and resale workflows.  
It combines computer vision + language intelligence to detect devices, validate user input, and classify condition as **Good / Average / Poor**.

## Key Features

- **YOLO Device Detection** with bounding boxes and confidence.
- **Manual vs AI Validation** gate before final approval.
- **VLM Condition + Damage Analysis** from cropped/boxed device regions.
- **Condition Classification** into showcase-ready outcomes:
  - `Good`
  - `Average`
  - `Poor`
- **Full-stack UI + API flow** for practical live demos and viva.

## Pipeline Flow

1. **YOLO Detection**
   - Detects device type from uploaded image(s).
   - Produces bounding boxes and confidence.
2. **Device Type Validation**
   - Compares YOLO device type with manual form input.
   - If mismatch: returns  
     **"AI scan and Manual input do not match"**.
3. **VLM Analysis**
   - Runs on boxed/cropped device image.
   - Evaluates condition and damage cues.
4. **Condition Classification**
   - Heavy damage -> **Poor**
   - Slight damage -> **Average**
   - No damage -> **Good**

## Tech Stack

- **ML/CV**: YOLO, VLM (BLIP-family based analysis path)
- **Backend**: FastAPI, Python
- **Frontend**: React + Vite
- **Data/Storage**: MongoDB + local support modules

## Project Structure

```text
SmartDeviceAI/
├─ backend/
│  ├─ app/                 # Dashboard/auth APIs and routes
│  ├─ services/            # AI service layer
│  ├─ models/              # Backend model assets/config
│  ├─ app.py               # AI inference API (port 5000)
│  ├─ pipeline.py          # YOLO -> Validation -> VLM flow
│  └─ requirements.txt
├─ frontend/
│  ├─ src/                 # React application
│  ├─ public/              # Static assets
│  └─ package.json
├─ models/                 # Root-level model artifacts
├─ scripts/                # Startup scripts
└─ README.md
```

## Quick Setup

### 1) Backend (Dashboard API)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2) AI Inference API

```bash
cd backend
.venv\Scripts\activate
python app.py
```

### 3) Frontend

```bash
cd frontend
npm install
npm run dev
```

## Example Output

- **Device Type**: `laptop`
- **Match Status**: `Match`
- **Condition**: `Poor` (or `Average` / `Good`)
- **Damage Signal**: `Broken` or `Not Broken`

---

Built for practical demonstrations, robust validation behavior, and polished project showcase delivery.

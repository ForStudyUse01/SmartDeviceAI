# E-waste Detection Pipeline - Installation & Quick Start

## ⚡ 5-Minute Quick Start

### Prerequisites
- Python 3.11+
- Node.js 16+
- 4GB+ RAM (16GB recommended for faster inference)

### Backend Setup (3 minutes)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the API server
python app.py
```

✅ API running at: `http://127.0.0.1:5000`
📚 API docs at: `http://127.0.0.1:5000/docs`

### Frontend Setup (2 minutes)

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
echo "VITE_AI_ANALYZE_URL=http://127.0.0.1:5000" > .env.local

# Start dev server
npm run dev
```

✅ Frontend at: `http://127.0.0.1:5173`

### Test It! (within 5 minutes)

1. Open browser: `http://127.0.0.1:5173`
2. Navigate to "Hybrid Vision Intelligence" (or E-waste Detection)
3. Upload an image
4. Click "Run Hybrid Analysis"
5. See results with bounding boxes!

---

## 📋 Full Installation Guide

### System Requirements

**Minimum:**
- CPU: i5-9400 or equivalent
- RAM: 4GB
- Storage: 10GB (models ~7GB)
- OS: Ubuntu 20.04+, Windows 10+, macOS 12+

**Recommended:**
- CPU: i7-10700K or higher
- RAM: 16GB
- Storage: 20GB
- GPU: NVIDIA RTX 3060 or better
- OS: Ubuntu 22.04 or Windows 11

### Step 1: Clone Repository

```bash
git clone <repo-url>
cd "SB Project - clone 2"
```

### Step 2: Backend Setup

```bash
cd backend

# Create Python virtual environment
python -m venv venv

# Activate environment
# Linux/Mac:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate.bat

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python -c "from ultralytics import YOLO; print('✅ YOLO OK')"
python -c "from transformers import Blip2Processor; print('✅ BLIP-2 OK')"
```

### Step 3: Download Models (on first run)

Models auto-download on first use. To pre-download:

```bash
python -c "
from ultralytics import YOLO
from transformers import Blip2Processor, Blip2ForConditionalGeneration
import torch

print('Downloading YOLO...')
YOLO('yolov8n.pt')

print('Downloading BLIP-2...')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
Blip2Processor.from_pretrained('Salesforce/blip2-opt-2.7b')
Blip2ForConditionalGeneration.from_pretrained('Salesforce/blip2-opt-2.7b', torch_dtype=torch.float16 if device == 'cuda' else torch.float32)

print('✅ All models downloaded!')
"
```

Expected download: ~7-10GB
Time: 5-15 minutes (depending on internet)

### Step 4: Frontend Setup

```bash
cd ../frontend

# Install Node dependencies
npm install

# Create environment file
cat > .env.local << EOF
VITE_API_URL=http://127.0.0.1:8000
VITE_AI_ANALYZE_URL=http://127.0.0.1:5000
EOF

# Verify installation
npm --version  # Should be 6.0+
node --version  # Should be 16.0+
```

### Step 5: Run Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python app.py
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:5000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Expected output:
```
VITE v4.4.0 running at:
  ➜  Local:   http://127.0.0.1:5173
```

### Step 6: Access Application

- **Frontend:** `http://127.0.0.1:5173`
- **API Docs:** `http://127.0.0.1:5000/docs`
- **API Health:** `http://127.0.0.1:5000/health`

---

## 🎯 Your First Analysis

### Via Web UI (Easiest)

1. Go to `http://127.0.0.1:5173`
2. Click "Hybrid Vision Intelligence" in navigation
3. Upload an image or multiple images
4. Click "Run Analysis"
5. View results with bounding boxes

### Via Command Line (Advanced)

```bash
# Single image
curl -X POST \
  -F "file=@image.jpg" \
  "http://127.0.0.1:5000/analyze?conf_threshold=0.25"

# Check health
curl http://127.0.0.1:5000/health

# View API docs
curl http://127.0.0.1:5000/docs
```

### Via Python Script

```python
# examples.py is included!
python backend/examples.py
```

---

## ⚙️ Configuration

### Environment Variables

Create `backend/.env`:
```env
# Optional: Enable GPU
CUDA_AVAILABLE=false

# Optional: Change port
PORT=5000

# Optional: Set debug mode
DEBUG=false
```

### API Settings

Edit `backend/app.py` to customize:

```python
# Change VLM model (line ~20)
pipeline = E_WasteDetectionPipeline(
    yolo_model_path="yolov8n.pt",  # options: yolov8s.pt, yolov8m.pt
    vlm_model_name="Salesforce/blip2-opt-2.7b"  # options: blip2-opt-6.7b
)
```

### CORS Settings

To allow other origins, edit `backend/app.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://example.com", "https://app.example.com"],
    # ...
)
```

---

## 🚀 Using the API

### Single Image Analysis

```bash
curl -X POST \
  -F "file=@device.jpg" \
  "http://127.0.0.1:5000/analyze?conf_threshold=0.25"
```

Response:
```json
{
  "status": "success",
  "image_name": "device.jpg",
  "num_detections": 2,
  "detected_objects": [
    {
      "yolo_label": "battery",
      "yolo_confidence": 92.5,
      "vlm_object": "lithium battery",
      "condition": "damaged",
      "suggestion": "Recycle at certified facility",
      "eco_score": 45,
      "box": [100, 150, 250, 280]
    }
  ]
}
```

### Batch Analysis (Multiple Images)

```bash
curl -X POST \
  -F "files=@img1.jpg" \
  -F "files=@img2.jpg" \
  -F "files=@img3.jpg" \
  "http://127.0.0.1:5000/analyze-batch?conf_threshold=0.25"
```

---

## 📊 YOLO Fine-Tuning

### Prepare Your Dataset

```
my_dataset/
├── images/
│   ├── train/    (80% of images)
│   ├── val/      (20% of images)
│   └── test/     (optional)
├── labels/
│   ├── train/    (.txt YOLO annotations)
│   └── val/
└── data.yaml
```

### data.yaml Structure

```yaml
path: /absolute/path/to/my_dataset
train: images/train
val: images/val
nc: 6  # Number of classes
names:
  0: battery
  1: pcb
  2: wire
  3: charger
  4: laptop
  5: mobile
```

### YOLO Annotation Format

Each image needs a `.txt` file with same name:
```
<class_id> <x_center> <y_center> <width> <height>
```

All values normalized to 0-1 range.

Example `image.txt`:
```
0 0.5 0.5 0.3 0.4
1 0.2 0.3 0.2 0.2
```

### Start Training

```bash
# Via CLI
cd backend
python train.py --data /path/to/data.yaml --epochs 50 --batch 8

# Via API
curl -X POST \
  "http://127.0.0.1:5000/train-yolo?data_yaml_path=/path/to/data.yaml&epochs=50&batch_size=8"
```

### Use Fine-tuned Model

```bash
# Load new model
curl -X POST \
  "http://127.0.0.1:5000/load-model?model_path=runs/detect/train10/weights/best.pt"

# Now all analyses use the new model!
```

---

## 🐛 Troubleshooting

### CUDA/GPU Issues

```bash
# Check if GPU is available
python -c "import torch; print(torch.cuda.is_available())"

# Force CPU mode (if GPU has issues)
export CUDA_VISIBLE_DEVICES=-1
python app.py
```

### Out of Memory (OOM)

```bash
# Use smaller model
# Edit app.py, change to:
vlm_model_name="Salesforce/blip2-opt-2.7b"

# Reduce batch size during training
python train.py --data data.yaml --batch 4
```

### Slow First Run

First run downloads models (~10 seconds per model). Subsequent runs are fast.

```bash
# Pre-download to speed up
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Model Download Issues

```bash
# Set custom cache directory
export HF_HOME=/path/to/cache
export YOLO_HOME=/path/to/yolo/cache
python app.py
```

### Port Already In Use

```bash
# Use different port
PORT=5001 python app.py
```

---

## 📦 Dependency Installation Issues

### If `pip install` fails:

```bash
# Upgrade pip first
python -m pip install --upgrade pip setuptools wheel

# Install with verbose output to debug
pip install -r requirements.txt -v

# Install individual packages if needed
pip install torch==2.0.0  # Specify version
pip install transformers==4.36.0
pip install ultralytics==8.3.0
```

### For GPU support (CUDA):

```bash
# Install CUDA-enabled PyTorch (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

## ✅ Verification Checklist

- [ ] Python 3.11+ installed
- [ ] Node.js 16+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (requirements.txt)
- [ ] Models downloaded (yolov8n.pt + BLIP-2)
- [ ] Backend running on port 5000
- [ ] Frontend running on port 5173
- [ ] Can access http://127.0.0.1:5173
- [ ] Can access http://127.0.0.1:5000/health
- [ ] Test image analysis works

---

## 📚 Next Steps

1. **Try Demo**: `python backend/examples.py`
2. **Prepare Dataset**: Follow YOLO annotation format
3. **Fine-tune**: Use `train.py` script
4. **Deploy**: Follow production deployment guide
5. **Integrate**: Use API in your own applications

---

## 🆘 Getting Help

- **API Documentation**: `http://localhost:5000/docs` (Swagger UI)
- **Full README**: See `README_EWASTE_PIPELINE.md`
- **Examples**: Check `backend/examples.py`
- **Training Guide**: See `README_EWASTE_PIPELINE.md` → YOLO Fine-tuning

---

## 📄 File Summary

| File | Purpose |
|------|---------|
| `app.py` | FastAPI main application |
| `pipeline.py` | YOLO + VLM orchestration |
| `yolo_model.py` | YOLO detection & training |
| `vlm_model.py` | BLIP-2 vision language model |
| `train.py` | Command-line training script |
| `examples.py` | Usage examples & demos |
| `frontend/src/pages/HybridAIPage.jsx` | Main UI component |
| `README_EWASTE_PIPELINE.md` | Full documentation |

---

## 💡 Tips for Best Results

1. **Use images 640x480 or larger** for better detection
2. **Adjust confidence threshold** (0.1-0.5) for your needs
3. **Use GPU** if available (10x faster)
4. **Fine-tune on your data** for 30%+ accuracy improvement
5. **Start with small batch size** (4-8) if low on RAM

---

Made with ❤️ for sustainable electronics recycling

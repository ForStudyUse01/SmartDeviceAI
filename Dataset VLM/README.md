# Dataset VLM

This folder stores raw datasets for VLM fine-tuning and source configuration.

## Sources configured

- Mobile:
  - https://universe.roboflow.com/datacluster-labs-agryi/mobile-phone-dataset/fork
  - https://universe.roboflow.com/team-ks/broken-electronic-objects
- Laptop:
  - https://universe.roboflow.com/team-ks/broken-laptop-parts
  - https://universe.roboflow.com/provod1337/new-v-laptop-broken

Tablet dataset is not configured yet due missing reliable public source.

## Generate training labels

1. Set API key:

```powershell
$env:ROBOFLOW_API_KEY="YOUR_KEY"
```

2. Run dataset prep:

```powershell
python scripts/prepare_vlm_dataset.py
```

This will:

- download datasets into `Dataset VLM/raw`
- generate:
  - `backend/data/vlm_train.jsonl`
  - `backend/data/vlm_val.jsonl`

## Start VLM fine-tuning

```powershell
cd backend
python train_vlm.py --train-jsonl data/vlm_train.jsonl --val-jsonl data/vlm_val.jsonl --image-root ".."
```

For quick smoke run:

```powershell
python train_vlm.py --train-jsonl data/vlm_train.jsonl --val-jsonl data/vlm_val.jsonl --image-root ".." --max-samples 200 --epochs 1
```

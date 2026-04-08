# SmartDeviceAI Models

- `best.pt` (project root) is the primary YOLOv8 checkpoint used by backend inference.
- Backend auto-discovers fallback checkpoints under `runs/**/weights/best.pt`.
- BLIP captioning model is loaded from Hugging Face at runtime (`Salesforce/blip-image-captioning-base`).


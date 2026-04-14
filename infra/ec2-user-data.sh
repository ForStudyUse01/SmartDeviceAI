#!/bin/bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip nginx docker.io
systemctl enable docker
systemctl start docker

# Local MongoDB for free-tier simplicity
docker rm -f smartdevice-mongo || true
docker run -d --name smartdevice-mongo --restart unless-stopped -p 127.0.0.1:27017:27017 mongo:7

if [ ! -d /opt/smartdeviceai ]; then
  git clone https://github.com/forstudyuse01/SmartDeviceAI.git /opt/smartdeviceai
else
  cd /opt/smartdeviceai
  git pull --ff-only
fi

cd /opt/smartdeviceai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cat >/etc/systemd/system/smartdevice-backend.service <<'EOF'
[Unit]
Description=SmartDeviceAI FastAPI Backend
After=network.target docker.service

[Service]
Type=simple
WorkingDirectory=/opt/smartdeviceai/backend
Environment="MONGODB_URI=mongodb://127.0.0.1:27017"
Environment="MONGODB_DB=smartdeviceai"
Environment="CORS_ORIGINS=*"
ExecStart=/opt/smartdeviceai/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/smartdevice-ai.service <<'EOF'
[Unit]
Description=SmartDeviceAI AI Inference API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/smartdeviceai/backend
Environment="FAST_AI_MODE=true"
Environment="CORS_ORIGINS=*"
ExecStart=/opt/smartdeviceai/backend/.venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/nginx/sites-available/default <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ai/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
EOF

systemctl daemon-reload
systemctl enable smartdevice-backend
systemctl restart smartdevice-backend
systemctl enable smartdevice-ai
systemctl restart smartdevice-ai
systemctl restart nginx

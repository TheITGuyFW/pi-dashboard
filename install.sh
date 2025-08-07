#!/bin/bash
set -e

echo "🔧 Installing dependencies..."
sudo apt update
sudo apt install -y python3-flask python3-psutil curl

echo "📦 Setting up systemd service..."
sudo cp pi-dashboard.service /etc/systemd/system/pi-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable pi-dashboard
sudo systemctl start pi-dashboard

echo "✅ Pi Dashboard installed. Access it at http://<your-pi-ip>:8080"

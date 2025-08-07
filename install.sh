#!/bin/bash

# ============================
# Pi Dashboard Installer
# ============================
# Author: Gabriel M. (ATG)
# Repo: https://github.com/TheITGuyFW/pi-dashboard
# Description: Installs Flask-based dashboard for system stats and 3CX management
# ============================

set -e

# === Define paths ===
APP_DIR="/home/pi/pi-dashboard"
SERVICE_FILE="/etc/systemd/system/pi-dashboard.service"

# === Create app directory ===
echo "📁 Creating project directory at $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# === Install dependencies ===
echo "🔧 Installing Python packages..."
sudo apt update
sudo apt install -y python3 python3-flask python3-psutil curl

# === Write Python app ===
cat <<EOF > pi-monitor-dashboard.py
from flask import Flask, render_template_string, request, jsonify
import psutil, socket, subprocess

app = Flask(__name__)
alerts_enabled = True
services = {"3CX SBC": "3cxsbc", "SSH": "ssh", "Cockpit": "cockpit"}
provisioning_info = {"fqdn": "", "authid": ""}

def get_status():
    return {
        "hostname": socket.getfqdn(),
        "ip": subprocess.getoutput("hostname -I").split()[0],
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "temp": subprocess.getoutput("vcgencmd measure_temp").replace("temp=", ""),
        "sbc_status": subprocess.getoutput("systemctl is-active 3cxsbc"),
        "services": {k: subprocess.getoutput(f"systemctl is-active {v}") for k,v in services.items()}
    }

@app.route('/')
def index():
    return render_template_string("""<html><head><title>Pi Dashboard</title>
    <script>
    function act(s, a) { fetch(`/service/${s}/${a}`, {method: 'POST'}).then(()=>location.reload()); }
    function send(action) {
      let fqdn = prompt('FQDN?'); let auth = prompt('AuthID?');
      fetch(`/3cx/${action}`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ fqdn: fqdn, authid: auth })
      }).then(()=>location.reload());
    }
    </script></head><body><h1>Pi Dashboard</h1>
    {% for k,v in data.items() if k not in ['services'] %}<p><b>{{k}}:</b> {{v}}</p>{% endfor %}
    <h3>Services</h3>
    {% for k,v in data['services'].items() %}<p><b>{{k}}</b> - {{v}}
    <button onclick="act('{{k | lower}}','start')">Start</button>
    <button onclick="act('{{k | lower}}','stop')">Stop</button>
    <button onclick="act('{{k | lower}}','restart')">Restart</button></p>{% endfor %}
    <h3>3CX Setup</h3>
    <button onclick="send('install')">Install 3CX</button>
    <button onclick="send('update')">Update 3CX</button>
</body></html>""", data=get_status())

@app.route('/service/<svc>/<action>', methods=['POST'])
def control(svc, action):
    subprocess.run(['sudo', 'systemctl', action, svc], check=False)
    return ('', 204)

@app.route('/3cx/<action>', methods=['POST'])
def provision(action):
    j = request.get_json(); fqdn = j.get('fqdn'); authid = j.get('authid')
    subprocess.run(['sudo', 'apt', 'remove', '-y', '3cxsbc'], check=False)
    subprocess.run(f"bash -c \"$(curl -sSL https://downloads-global.3cx.com/downloads/sbc/3cxsbcsetup.sh)\" -- --provisioning-url https://{fqdn}:5001?auth={authid}", shell=True)
    return ('', 204)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
EOF

# === Write systemd service ===
cat <<EOF | sudo tee $SERVICE_FILE
[Unit]
Description=Pi Dashboard Flask Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $APP_DIR/pi-monitor-dashboard.py
WorkingDirectory=$APP_DIR
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

# === Enable and start service ===
sudo systemctl daemon-reload
sudo systemctl enable pi-dashboard
sudo systemctl start pi-dashboard

# === Done ===
echo "✅ Pi Dashboard installed. Visit: http://<your-pi-ip>:8080"

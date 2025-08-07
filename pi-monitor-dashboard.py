from flask import Flask, render_template_string, request, jsonify
import psutil
import socket
import subprocess
import threading
import time
import os

app = Flask(__name__)

alerts_enabled = True
previous_cpu = 0

# Services to monitor and control
services = {
    "3CX SBC": "3cxsbc",
    "SSH": "ssh",
    "Cockpit": "cockpit"
}

provisioning_info = {"fqdn": "", "authid": ""}

# ---------------------- Helper Functions ----------------------

def get_cpu_temp():
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        return temp.replace("temp=", "").strip()
    except:
        return "Unavailable"

def get_ip():
    try:
        ip = subprocess.check_output(['hostname', '-I']).decode().split()[0]
        return ip
    except:
        return "Unknown"

def get_hostname():
    try:
        fqdn = socket.getfqdn()
        return fqdn
    except:
        return "Unknown"

def get_service_status(service):
    try:
        status = subprocess.run(['systemctl', 'is-active', service], capture_output=True, text=True)
        return status.stdout.strip()
    except:
        return "Unknown"

def control_service(service, action):
    try:
        subprocess.run(["sudo", "systemctl", action, service], check=True)
        return f"{action.capitalize()}ed {service}"
    except subprocess.CalledProcessError:
        return f"Failed to {action} {service}"

# ---------------------- Web Interface Routes ----------------------

@app.route('/')
def dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pi Monitor Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f2f2f2; padding: 20px; }
            h1 { color: #333; }
            .card { background: white; border-radius: 10px; padding: 20px; margin: 10px 0; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            .status-ok { color: green; font-weight: bold; }
            .status-fail { color: red; font-weight: bold; }
            button { padding: 5px 10px; margin: 5px; }
        </style>
        <script>
            let lastCpu = 0;
            function fetchData() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById("hostname").innerText = data.hostname;
                        document.getElementById("ip").innerText = data.ip;
                        document.getElementById("cpu").innerText = data.cpu + "%";
                        document.getElementById("ram").innerText = data.ram + "%";
                        document.getElementById("disk").innerText = data.disk + "%";
                        document.getElementById("temp").innerText = data.temp;
                        document.getElementById("sbc_status").innerText = data.sbc_status;
                        document.getElementById("sbc_status").className = (data.sbc_status === 'active') ? 'status-ok' : 'status-fail';
                        for (const key in data.services) {
                            document.getElementById("status-" + key).innerText = data.services[key];
                        }
                        if (Math.abs(lastCpu - data.cpu) >= 5) {
                            lastCpu = data.cpu;
                            setTimeout(fetchData, 500);
                        } else {
                            setTimeout(fetchData, 2000);
                        }
                    });
            }
            function toggleAlerts() {
                fetch('/toggle_alerts', { method: 'POST' });
            }
            function control(service, action) {
                fetch(`/service/${service}/${action}`, { method: 'POST' })
                    .then(() => fetchData());
            }
            function rebootNow() {
                fetch('/power/reboot', { method: 'POST' });
            }
            function shutdownNow() {
                fetch('/power/shutdown', { method: 'POST' });
            }
            function scheduleReboot(minutes) {
                fetch(`/power/schedule_reboot/${minutes}`, { method: 'POST' });
            }
            function submitProvisioning(action) {
                const fqdn = prompt("Enter FQDN:", "test.in.3cx.us");
                const authid = prompt("Enter Auth ID:", "abcdef123456");
                fetch(`/3cx/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fqdn: fqdn, authid: authid })
                }).then(() => fetchData());
            }
            window.onload = fetchData;
        </script>
    </head>
    <body>
        <h1>Raspberry Pi Monitoring Dashboard</h1>

        <div class="card">
            <strong>Device FQDN:</strong> <span id="hostname"></span><br>
            <strong>IP Address:</strong> <span id="ip"></span><br>
        </div>

        <div class="card">
            <strong>CPU Usage:</strong> <span id="cpu"></span><br>
            <strong>RAM Usage:</strong> <span id="ram"></span><br>
            <strong>Disk Usage:</strong> <span id="disk"></span><br>
            <strong>Temperature:</strong> <span id="temp"></span><br>
        </div>

        <div class="card">
            <strong>3CX SBC Service:</strong>
            <span id="sbc_status"></span>
            <button onclick="control('3cxsbc','restart')">Restart SBC</button>
            <button onclick="submitProvisioning('install')">Install 3CX</button>
            <button onclick="submitProvisioning('update')">Update 3CX</button>
        </div>

        <div class="card">
            <h3>Service Controls</h3>
            {% for label, svc in services.items() %}
                <strong>{{ label }}:</strong> <span id="status-{{ svc }}"></span><br>
                <button onclick="control('{{ svc }}','start')">Start</button>
                <button onclick="control('{{ svc }}','stop')">Stop</button>
                <button onclick="control('{{ svc }}','restart')">Restart</button><br><br>
            {% endfor %}
        </div>

        <div class="card">
            <h3>Power Options</h3>
            <button onclick="rebootNow()">Reboot Now</button>
            <button onclick="shutdownNow()">Shutdown Now</button>
            <button onclick="scheduleReboot(5)">Reboot in 5 minutes</button>
        </div>

        <div class="card">
            <button onclick="toggleAlerts()">Toggle Alerts</button>
        </div>
    </body>
    </html>
    """, services=services)

@app.route('/status')
def status():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return jsonify({
        "hostname": get_hostname(),
        "ip": get_ip(),
        "cpu": cpu_percent,
        "ram": memory.percent,
        "disk": disk.percent,
        "temp": get_cpu_temp(),
        "sbc_status": get_service_status("3cxsbc"),
        "services": {k: get_service_status(v) for k, v in services.items()}
    })

@app.route('/toggle_alerts', methods=['POST'])
def toggle_alerts():
    global alerts_enabled
    alerts_enabled = not alerts_enabled
    return ('', 204)

@app.route('/service/<svc>/<action>', methods=['POST'])
def control(svc, action):
    return jsonify({"result": control_service(svc, action)})

@app.route('/power/reboot', methods=['POST'])
def power_reboot():
    subprocess.run(['sudo', 'reboot'])
    return ('', 204)

@app.route('/power/shutdown', methods=['POST'])
def power_shutdown():
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])
    return ('', 204)

@app.route('/power/schedule_reboot/<int:minutes>', methods=['POST'])
def schedule_reboot(minutes):
    subprocess.run(['sudo', 'shutdown', '-r', f'+{minutes}'])
    return ('', 204)

@app.route('/3cx/<action>', methods=['POST'])
def manage_3cx(action):
    global provisioning_info
    data = request.get_json()
    fqdn = data.get('fqdn')
    authid = data.get('authid')
    provisioning_info['fqdn'] = fqdn
    provisioning_info['authid'] = authid

    if action == 'install' or action == 'update':
        subprocess.run(['sudo', 'apt', 'remove', '-y', '3cxsbc'], check=False)
        install_cmd = f"bash -c \"$(curl -sSL https://downloads-global.3cx.com/downloads/sbc/3cxsbcsetup.sh)\" -- --provisioning-url https://{fqdn}:5001?auth={authid}"
        subprocess.run(install_cmd, shell=True)
    return ('', 204)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

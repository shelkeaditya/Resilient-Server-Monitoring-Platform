from flask import Flask, jsonify, render_template
import subprocess
import time
import threading

app = Flask(__name__)

cache = {
    "data": {},
    "last_updated": 0
}

def run_kubectl(cmd):
    try:
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
        return result.decode("utf-8")
    except:
        return "Error"

def update_cache():
    while True:
        pods = run_kubectl("kubectl get pods --no-headers")
        cpu = run_kubectl("kubectl top pods --no-headers")

        # get first pod for logs
        pod_name = ""

        if pods and pods != "Error":
            lines = [l for l in pods.split("\n") if l.strip()]
    
    for line in lines:
        name = line.split()[0]
        
        # skip system / flask pods if needed
        if "anomaly-app" in name:
            pod_name = name
            break
        # safe logs fetch
        logs = "No logs available"

        if pod_name:
            try:
                logs = subprocess.check_output(
                    f"kubectl logs {pod_name} --tail=50",
                    shell=True,
                    stderr=subprocess.STDOUT
                ).decode("utf-8")
            except subprocess.CalledProcessError as e:
                logs = e.output.decode("utf-8")

        cache["data"] = {
            "pods": pods,
            "cpu": cpu,
            "logs": logs
        }

        cache["last_updated"] = time.time()
        time.sleep(3)

# background thread
threading.Thread(target=update_cache, daemon=True).start()

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/data")
def data():
    return jsonify(cache["data"])

if __name__ == "__main__":
    app.run(debug=True)

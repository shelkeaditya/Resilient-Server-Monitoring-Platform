import os
import time
import subprocess

THRESHOLD = 20  # adjust if needed

def get_cpu():
    try:
        output = subprocess.check_output(
            ["kubectl", "top", "pods", "--no-headers"],
            text=True
        )

        for line in output.split("\n"):
            if "anomaly-app" in line:
                cpu = line.split()[1]  # e.g. 5m
                return int(cpu.replace("m", ""))
    except Exception as e:
        print("Error:", e)

    return 0


while True:
    cpu = get_cpu()
    print(f"[INFO] CPU: {cpu}m")

    # 🔥 Write to file for Flask UI
    with open("status.txt", "w") as f:
        f.write(f"CPU Usage: {cpu}m\n")

    if cpu > THRESHOLD:
        print("[ALERT] High CPU → Restarting deployment")
        os.system("kubectl rollout restart deployment anomaly-app")

    time.sleep(10)

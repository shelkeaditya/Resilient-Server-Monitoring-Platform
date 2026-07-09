# Resilient Server Monitoring Platform

> A cloud-native server monitoring and self-healing platform that continuously monitors system health, detects failures in real time, and automatically performs recovery actions to improve infrastructure reliability.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-black)
![Docker](https://img.shields.io/badge/Docker-Container-blue)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Orchestration-326CE5)
![License](https://img.shields.io/badge/License-MIT-green)

---

# Overview

The **Resilient Server Monitoring Platform** is an intelligent infrastructure monitoring solution designed to improve server availability by combining **real-time monitoring**, **automated alerting**, and **self-healing mechanisms**.

Instead of simply displaying server metrics, the platform actively detects unhealthy services, performs automated recovery actions, and provides administrators with a centralized dashboard for monitoring the health of their infrastructure.

The project demonstrates modern **DevOps**, **Cloud Computing**, and **Site Reliability Engineering (SRE)** practices using technologies like Docker, Kubernetes, Prometheus, Grafana, Python, and Flask.

---

# Problem Statement

Traditional monitoring tools notify administrators after failures occur.

This project goes one step further by:

- Detecting issues automatically
- Triggering recovery actions
- Reducing downtime
- Improving service reliability
- Providing real-time monitoring dashboards

---

# Features

## Real-Time Monitoring

- CPU Usage Monitoring
- Memory Usage Monitoring
- Disk Usage Monitoring
- Network Statistics
- Process Monitoring
- Service Health Checks

---

## Alerting System

- High CPU Alerts
- High Memory Alerts
- Low Disk Space Alerts
- Service Failure Alerts
- Container Health Alerts

---

## Self-Healing

Automatically performs recovery actions such as:

- Restart failed services
- Restart Docker containers
- Restart Kubernetes Pods
- Recover crashed applications
- Execute custom recovery scripts

---

## Dashboard

Interactive monitoring dashboard showing:

- Live CPU usage
- Memory utilization
- Disk usage
- Running services
- Pod status
- Container status
- System uptime
- Server logs

---

## Logging

- Application Logs
- Recovery Logs
- Error Logs
- Monitoring History

---

## Cloud Ready

Supports deployment on

- AWS EC2
- Azure VM
- Google Cloud VM
- Local Server
- Virtual Machines
- Kubernetes Cluster

---

# Architecture

```
             +------------------+
             |   Web Dashboard  |
             |     (Flask)      |
             +---------+--------+
                       |
                       |
             +---------v--------+
             | Monitoring Agent |
             +---------+--------+
                       |
     +-----------------+----------------+
     |                 |                |
+----v----+      +-----v-----+     +----v----+
| CPU     |      | Memory    |     | Disk    |
+---------+      +-----------+     +---------+
                       |
                       |
               +-------v--------+
               | Alert Manager  |
               +-------+--------+
                       |
               +-------v--------+
               | Self Healing   |
               +-------+--------+
                       |
               Restart Services
               Restart Containers
               Restart Pods
```

---

# Tech Stack

## Backend

- Python
- Flask

## Monitoring

- psutil
- Prometheus
- Node Exporter

## Visualization

- Grafana

## Containerization

- Docker

## Orchestration

- Kubernetes

## Automation

- Bash
- Cron Jobs

## Version Control

- Git
- GitHub

---

# 📂 Project Structure

```
Resilient-Server-Monitoring-Platform/

│
├── app.py
├── requirements.txt
├── monitoring/
│   ├── cpu.py
│   ├── memory.py
│   ├── disk.py
│   └── network.py
│
├── self_healing/
│   ├── restart_service.py
│   ├── restart_container.py
│   └── recovery.py
│
├── dashboard/
│   ├── templates/
│   ├── static/
│   └── routes.py
│
├── logs/
│
├── docker/
│
├── kubernetes/
│
└── README.md
```

---

# ⚙ Installation

## Clone Repository

```bash
git clone https://github.com/shelkeaditya/Resilient-Server-Monitoring-Platform.git

cd Resilient-Server-Monitoring-Platform
```

---

## Create Virtual Environment

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

### Linux

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run Application

```bash
python app.py
```

---

Open your browser:

```
http://localhost:5000
```

---

# Docker Deployment

Build Docker Image

```bash
docker build -t resilient-monitor .
```

Run Container

```bash
docker run -p 5000:5000 resilient-monitor
```

---

# Kubernetes Deployment

Apply manifests

```bash
kubectl apply -f kubernetes/
```

Check pods

```bash
kubectl get pods
```

View services

```bash
kubectl get svc
```

---

# Monitoring Metrics

The platform monitors:

- CPU Usage
- Memory Usage
- Disk Usage
- Disk I/O
- Network Traffic
- System Load
- Running Processes
- Docker Containers
- Kubernetes Pods
- Application Health

---

# Self-Healing Workflow

1. Monitor server metrics
2. Detect unhealthy state
3. Generate alert
4. Execute recovery script
5. Verify service recovery
6. Log recovery status
7. Update dashboard

---

# Future Improvements

- Email Notifications
- Slack Integration
- Microsoft Teams Alerts
- AI-based Anomaly Detection
- Predictive Failure Analysis
- Mobile Dashboard
- Multi-server Monitoring
- Distributed Agent Architecture
- RBAC Authentication
- Historical Analytics

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature/new-feature
```

3. Commit changes

```bash
git commit -m "Added new feature"
```

4. Push branch

```bash
git push origin feature/new-feature
```

5. Open a Pull Request

---

# 📜 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

**Aditya Shelke**

Cloud Engineer • DevSecOps • Kubernetes • AWS

GitHub: https://github.com/shelkeaditya

LinkedIn: https://linkedin.com/in/shelkeaditya

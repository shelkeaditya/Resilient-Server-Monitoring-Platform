FROM python:3.10-slim

WORKDIR /app

COPY app/ .

RUN pip install -r requirements.txt

# install kubectl
RUN apt update && apt install -y curl \
    && curl -LO "https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

CMD ["python", "app.py"]

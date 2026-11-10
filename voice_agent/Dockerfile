FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .
# Download the VAD model at build time so cold starts are fast.
RUN python agent.py download-files
CMD ["python", "agent.py", "start"]

FROM python:3.11-slim

# zoneinfo needs tzdata for non-UTC timezones (scheduler IST)
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Kolkata

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: write CSVs under /app/output
CMD ["python", "main.py", "--output-dir", "/app/output"]

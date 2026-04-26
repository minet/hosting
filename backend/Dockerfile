FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends nmap && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY CHARTE.md /charte/CHARTE.md
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]

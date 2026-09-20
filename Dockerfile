FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg supervisor && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

RUN mkdir -p /tmp/omnipull

COPY supervisord.conf /etc/supervisor/conf.d/omnipull.conf

EXPOSE 8000

CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]

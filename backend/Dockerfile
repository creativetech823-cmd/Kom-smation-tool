# Built from backend/ (see render.yaml's dockerContext). Video rendering
# (Remotion) is not deployed yet, so no Node.js/Chromium here — Python only.

FROM python:3.11-slim-bookworm

WORKDIR /app

# --- Python deps ---
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- App code ---
COPY . .

RUN mkdir -p renders audio motion reference_uploads visuals

# Render injects $PORT at runtime; the app must bind to it, not a hardcoded port.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT

FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "mcp[cli]>=1.0.0" uvicorn

COPY server.py .

ENV PORT=8002
EXPOSE 8002

CMD ["python", "server.py"]

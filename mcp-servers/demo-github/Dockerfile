FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "mcp[cli]>=1.0.0" uvicorn

COPY server.py .

ENV PORT=8001
EXPOSE 8001

CMD ["python", "server.py"]

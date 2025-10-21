# Use slim Python base
FROM python:3.12-alpine

WORKDIR /app
COPY server.py client.py README.md ./ 
COPY content ./content

# Default envs (override in docker-compose or docker run)
ENV PORT=8080 \
    THREADING_MODE=threaded \
    POOL_SIZE=8 \
    HANDLER_DELAY_MS=1000 \
    COUNTER_MODE=locked \
    RATE_LIMIT_RPS=5 \
    RATE_LIMIT_BURST=5 \
    CONTENT_ROOT=content

EXPOSE 8080
CMD ["python", "server.py"]

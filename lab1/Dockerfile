FROM python:3.12-slim
WORKDIR /app

# copy server and the static content into the image
COPY server.py /app/server.py
COPY content/ /app/content/

EXPOSE 8080

# serve the actual folder we just copied
CMD ["python", "/app/server.py", "/app/content", "--host", "0.0.0.0", "--port", "8080"]

# PR Lab 1 – HTTP File Server (Sockets + Docker Compose)

This repository contains a minimal HTTP file server built over raw TCP sockets,
plus an optional HTTP client, Dockerfile, and Docker Compose for easy running.

## Quickstart
```bash
docker compose up --build
# open http://localhost:8080/
```

## Run locally (without Docker)
```bash
python3 server.py ./content --host 0.0.0.0 --port 8080
```

## Client (optional)
```bash
python3 client.py 127.0.0.1 8080 / downloads
python3 client.py 127.0.0.1 8080 /image.png downloads
python3 client.py 127.0.0.1 8080 /sample.pdf downloads
python3 client.py 127.0.0.1 8080 /books/ downloads
```

## Folder structure
```
pr-lab1/
├─ server.py
├─ client.py
├─ Dockerfile
├─ docker-compose.yml
├─ README.md
└─ content/
   ├─ index.html
   ├─ image.png
   ├─ sample.pdf
   └─ books/
      ├─ book1.pdf
      └─ cover.png
```

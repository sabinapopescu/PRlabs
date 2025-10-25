# Lab 1 — HTTP File Server (TCP Sockets + Docker)

**Author:** Sabina Popescu (FAF-233)

## 1) Purpose & Scope
Build a **minimal HTTP/1.1 file server** over raw **TCP sockets** and run it reproducibly in Docker.  
Lab-1 focuses on correctness and protocol handling, not performance.

**Supported features**
- Methods: **GET** (and **HEAD** for tooling/tests)
- MIME whitelist: **`.html`**, **`.png`**, **`.pdf`** (and **`.ico`** to quiet browser favicon probes)
- Directory handling: list directory contents; serve `index.html` if requested explicitly
- Safe file mapping (prevents `../` traversal)
- Correct headers: `Date`, `Server`, `Content-Type`, `Content-Length`, `Connection: close`

**Out of scope (Lab-2):** concurrency/thread pool, race-condition demo, rate-limiting.

---

## 2) Project Layout
```
lab1/
├─ content/                 # served root
│  ├─ index.html
│  ├─ image.png
│  ├─ sample.pdf
│  └─ books/
│     ├─ book1.pdf
│     └─ cover.png
├─ client.py                # optional test client (GET)
├─ server.py                # single-connection HTTP server
├─ Dockerfile
├─ docker-compose.yml
└─ README.md                # this report
```

---

## 3) Server Implementation (high-level)
- Accept TCP, read until `\r\n\r\n`, parse request line and headers.
- **Path resolution:** strip `?query`/`#fragment`, URL-decode, join with root, reject escape outside root.
- **Response builder:** status line + headers + optional body; always sets `Content-Length`.
- **GET/HEAD logic:** HEAD returns headers only with correct length.
- **MIME whitelist:** unknown extensions ⇒ **404 Not Found**.
- **Security:** traversal outside root ⇒ **403 Forbidden**.

---

## 4) Dockerization

### `Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY server.py /app/server.py
EXPOSE 8080
CMD ["python", "/app/server.py", "/data", "--host", "0.0.0.0", "--port", "8080"]
```

### `docker-compose.yml` (Lab-1 service on port **8081**)
```yaml
services:
  web:
    build:
      context: .
    image: pr-lab1-httpfs:latest
    container_name: pr-lab1-web
    ports:
      - "8081:8080"
    volumes:
      - ./content:/data:ro   # serve host ./content inside container as /data
```

---

## 5) Run Instructions

```bash
cd lab1
docker compose down
docker compose up -d --build

# verify it's up
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep pr-lab1-web
docker logs --tail=20 pr-lab1-web
```

**Expected log line**
```
[INFO] Serving '/data' at http://0.0.0.0:8080 (one request at a time)
```

**Stop**
```bash
docker compose down
```

---

## 6) Quick Functional Tests

### Browser
- `http://localhost:8081/`           → directory listing of `/content`
- `http://localhost:8081/index.html` → renders HTML (may reference `/image.png`)
- `http://localhost:8081/image.png`  → displays PNG
- `http://localhost:8081/sample.pdf` → displays/opens PDF
- `http://localhost:8081/not-here.pdf` → **404 Not Found**

### `curl`
```bash
# HEAD sanity (should be 200)
curl -I http://localhost:8081/
curl -I http://localhost:8081/index.html

# GET (show headers; discard bodies for binaries)
curl -v http://localhost:8081/index.html
curl -v http://localhost:8081/image.png   --output /dev/null
curl -v http://localhost:8081/sample.pdf  --output /dev/null

# Directory listing
curl -v http://localhost:8081/
curl -v http://localhost:8081/books/

# Negative tests
curl -v http://localhost:8081/not-here.pdf
curl -v -X POST http://localhost:8081/                 # 405 Method Not Allowed
curl -v "http://localhost:8081/../../etc/passwd"       # 403 Forbidden
```

---

## 7) Optional Client Usage

```bash
# Print listing
python3 client.py 127.0.0.1 8081 / downloads

# Save binaries
python3 client.py 127.0.0.1 8081 /image.png  downloads
python3 client.py 127.0.0.1 8081 /sample.pdf downloads

# Subdirectory listing
python3 client.py 127.0.0.1 8081 /books/ downloads
```

The client prints HTML bodies to stdout and saves PNG/PDF to the chosen folder.

---

## 8) Troubleshooting (common)

- **`curl -I` returns 405**  
  You’re running an older `server.py` without HEAD support. Use the current version (GET+HEAD).

- **Intermittent 404s**  
  Ensure files really exist under `lab1/content/...`. Remember: only `.html/.png/.pdf/.ico` are served.

- **Nothing loads**  
  Check mapping and port: `volumes: ./content:/data:ro` and `8081:8080`.  
  Confirm: `docker logs pr-lab1-web` and `docker ps`.

- **Container name conflict**  
  `docker rm -f pr-lab1-web` then `docker compose up -d --build`.

---

## 9) Screenshot (put under `lab1/screenshots/`)

1. `docker compose up -d --build` output — `docker_up.png`
<img width="1305" height="424" alt="image" src="https://github.com/user-attachments/assets/f796e94b-8f29-4e9e-97bc-dd7524bca612" />

2. Running container (`docker ps` line) — `docker_ps.png`
<img width="1480" height="47" alt="image" src="https://github.com/user-attachments/assets/1d4ddcf7-6588-4946-8096-f5195b632515" />

4. Browser: `/` listing — `listing_root.png`  
<img width="826" height="331" alt="image" src="https://github.com/user-attachments/assets/215611de-f944-4d46-8da1-ff50080dfa18" />

5. Browser: `/index.html` — `index_html.png`  
<img width="1792" height="1071" alt="image" src="https://github.com/user-attachments/assets/49145c3d-a5ea-4820-8de0-679531c3baf6" />

6. Browser: `/image.png` — `image_png.png` 
<img width="1791" height="1078" alt="image" src="https://github.com/user-attachments/assets/976e6cf3-da79-4e94-a8da-8a305e22a739" />

7. Browser: `/sample.pdf` — `pdf_ok.png`  
<img width="1785" height="1078" alt="image" src="https://github.com/user-attachments/assets/2459621e-dc52-4c71-a0b4-ac42a9e7f1aa" />

8. `curl -I` for `/` and `/index.html` (200) — `curl_head.png` 
<img width="499" height="112" alt="image" src="https://github.com/user-attachments/assets/aa80b70c-8ba3-4979-9dc6-50052a5783d6" />

9. Negative tests (`404`, `405`, `403`) — `curl_negatives.png`
<img width="544" height="586" alt="image" src="https://github.com/user-attachments/assets/f8ba4d03-5f18-4f04-ab77-0d2b93200238" />

---

## 10) Conclusion
Lab-1 demonstrates a correct, minimal HTTP server over raw sockets with safe path resolution, MIME-aware responses, directory listings, and reproducible Docker packaging. It forms the baseline for Lab-2, where we will add concurrency, race-condition analysis, and rate-limiting.

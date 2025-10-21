# Lab 1: HTTP File Server with TCP Sockets

**Author:** Sabina Popescu, **FAF-233**

## 1. Introduction
This laboratory work implements a minimal **HTTP file server** using **Python TCP sockets** and **Docker Compose**.  
The server serves files from a chosen root directory and supports:
- **HTML** pages (text/html)
- **PNG** images (image/png)
- **PDF** documents (application/pdf)

Unknown extensions return **404 Not Found**.  
The project also includes an **optional Python client** that:
- prints HTML/directory listing bodies to stdout
- saves PNG/PDF responses to a local folder

Everything runs reproducibly via Docker Compose.

---

## 2. Source Directory Contents

Repository layout (this lab lives in `./lab1`):

```
lab1/
├─ content/                 # served root (HTML, PNG, PDF, subfolders)
│  ├─ index.html
│  ├─ image.png
│  ├─ sample.pdf
│  └─ books/
│     ├─ book1.pdf
│     └─ cover.png
├─ client.py                # optional client (GET-only)
├─ server.py                # single-connection HTTP socket server
├─ Dockerfile               # server image
├─ docker-compose.yml       # one service: httpfs
└─ README.md                # this report
```

> Add your proof images under `lab1/screenshots/` and keep the same names as below.

**Visual tree:**  
![screenshots/full_dir.png](screenshots/full_dir.png)

---

## 3. Docker Containerization

### Dockerfile (server)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY server.py /app/server.py
EXPOSE 8080
# The served directory is provided by a volume at /data (see docker-compose)
CMD ["python", "/app/server.py", "/data", "--host", "0.0.0.0", "--port", "8080"]
```

### docker-compose.yml
```yaml
services:
  httpfs:
    build: .
    container_name: httpfs
    ports:
      - "8080:8080"
    volumes:
      - ./content:/data:ro
```

> `./content` on the host is mounted read-only at `/data` in the container.

---

## 4. Starting the Container

From inside `lab1/`:

```bash
docker compose up --build -d
docker compose ps
```

**Expected logs:**
```
[INFO] Serving '/data' at http://0.0.0.0:8080 (one request at a time)
```

**Screenshots:**
- Build output: ![screenshots/docker_build.png](screenshots/docker_build.png)  
- Running service: ![screenshots/docker_up.png](screenshots/docker_up.png)

To stop:
```bash
docker compose down
```

---

## 5. Running the Server Locally (no Docker)

```bash
python3 server.py ./content --host 0.0.0.0 --port 8080
```

**Screenshot (terminal):**  
![screenshots/opened_server.png](screenshots/opened_server.png)

---

## 6. Contents of the Served Directory

The root `/data` (host `./content`) contains:

- `index.html` (references an image via `<img src="/image.png">`)
- `image.png`
- `sample.pdf`
- `books/` (subdirectory with `book1.pdf`, `cover.png`)

**Screenshot (file tree):**  
![screenshots/served_dir.png](screenshots/served_dir.png)

---

## 7. Required Browser Tests (4 cases)

1) **HTML with image**
```
http://localhost:8080/index.html
```
![screenshots/html_success.png](screenshots/html_success.png)

2) **PDF file**
```
http://localhost:8080/sample.pdf
```
![screenshots/pdf_success.png](screenshots/pdf_success.png)

3) **PNG file**
```
http://localhost:8080/image.png
```
![screenshots/png_success.png](screenshots/png_success.png)

4) **Inexistent file (404)**
```
http://localhost:8080/not-here.pdf
```
![screenshots/inexistent_fail.png](screenshots/inexistent_fail.png)

---

## 8. cURL Verifications (headers + statuses)

```bash
# HTML
curl -v http://localhost:8080/index.html

# PNG (discard body)
curl -v http://localhost:8080/image.png --output /dev/null

# PDF (discard body)
curl -v http://localhost:8080/sample.pdf --output /dev/null

# Directory listings
curl -v http://localhost:8080/
curl -v http://localhost:8080/books/

# 404
curl -v http://localhost:8080/not-here.pdf

# 405 for non-GET
curl -v -X POST http://localhost:8080/

# Path traversal blocked (expect 403)
curl -v "http://localhost:8080/../../etc/passwd"
```

**Screenshot (selected headers):**  
![screenshots/curl_headers.png](screenshots/curl_headers.png)

---

## 9. Client Script — Demonstration (Optional +2 pts)

Run while the container is up:

```bash
# Print root directory listing (HTML)
python3 client.py 127.0.0.1 8080 / downloads

# Save PNG/PDF to 'downloads' folder (created if missing)
python3 client.py 127.0.0.1 8080 /image.png downloads
python3 client.py 127.0.0.1 8080 /sample.pdf downloads

# Print subdirectory listing
python3 client.py 127.0.0.1 8080 /books/ downloads
```

**Screenshots:**
- Client console: ![screenshots/docker_up_client.png](screenshots/docker_up_client.png)  
- Saved files: ![screenshots/downloads.png](screenshots/downloads.png)

---

## 10. Directory Listing — Demonstration

Root listing (`/`) shows files and folders with links; subdirectory listing (`/books/`) shows PDFs/PNGs and a parent link.

- Root:
  ![screenshots/main_page.png](screenshots/main_page.png)
- Subdirectory:
  ![screenshots/subdirectory.png](screenshots/subdirectory.png)

---

## 11. Client Connecting from Another Machine (LAN)

**Server (my laptop):**
1. Ensure container is running (`docker compose up -d`).
2. Find IPv4:
   - **macOS**
     ```bash
     ipconfig getifaddr "$(route get default 2>/dev/null | awk '/interface:/{print $2}')"
     ```
   - **Windows**
     ```powershell
     ipconfig
     ```
3. Self-test:
   ```bash
   curl -v http://<my-ip>:8080/
   ```

**Client (friend’s laptop on same Wi‑Fi):**
- Open in browser: `http://<my-ip>:8080/`
- Or run my client:
  ```bash
  python3 client.py <my-ip> 8080 /books/book1.pdf downloads
  ```

**Screenshots:**
- My IP: ![screenshots/ipconfig.png](screenshots/ipconfig.png)  
- Friend viewing/downloading: ![screenshots/computer2.png](screenshots/computer2.png)

> Some guest/campus Wi‑Fi networks block device‑to‑device traffic (AP isolation). If so, use another network or a phone hotspot.

---

## 12. Implementation Notes

- **Protocol:** HTTP/1.1, single request per TCP connection (server closes after response).  
- **Headers used:** `Content-Type`, `Content-Length`, `Date`, `Connection`, `Server`, `Allow` (for 405).  
- **Security:** Blocks path traversal by comparing `realpath` of requested path against the root directory.  
- **MIME whitelist:** `.html`, `.png`, `.pdf` (unknown → 404).  
- **Directory listing:** dynamically generated HTML with links and parent navigation.

---

## 13. How to Reproduce (TA quick start)

```bash
cd lab1
docker compose up --build -d
# Then visit:
#   http://localhost:8080/
#   http://localhost:8080/index.html
#   http://localhost:8080/image.png
#   http://localhost:8080/sample.pdf
#   http://localhost:8080/not-here.pdf
```

---

## 14. Conclusions

The lab demonstrates how **application-level protocols (HTTP)** run over **transport (TCP)** with manual parsing, correct header construction, MIME typing, and safe filesystem mapping.  
Docker Compose ensures the grader can reproduce the environment consistently.  
The optional client validates the end-to-end flow for **HTML rendering** and **binary file downloads**.






<!-- # PR Lab 1 – HTTP File Server (Sockets + Docker Compose)

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
``` -->

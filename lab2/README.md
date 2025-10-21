# Lab 2: Concurrent HTTP Server — Multithreading, Race Conditions, and Locks

**Author:** Popescu Sabina, **FAF-233**

## 1. Introduction
This laboratory work implements and compares **concurrent HTTP servers** using **multithreading** under two scenarios:
- **Race condition present** (no synchronization)
- **Race condition handled** (using a thread lock)

To establish a baseline, a **single‑threaded** server is also included. We compare elapsed times for handling **10 requests** across all variants. For realism, each request simulates ~1s of work, and servers enforce a **rate limit = 5 requests/second**.

The lab also includes client scripts for both single‑threaded and multi‑threaded scenarios to generate controlled load and measure end‑to‑end timing.

---

## 2. Source Directory Contents (`./lab2`)
### Server scripts
- **`singlethreaded_server.py`** — handles one request at a time and measures total time for N requests.
- **`multithreaded_server_no_lock.py`** — concurrent server with `RATE_LIMIT=5`, intentionally **no locks** to exhibit a race condition.
- **`multithreaded_server_lock.py`** — same as above but **adds thread locks** to remove the race.

### Client scripts
- **`client.py`** — load generator for the multithreaded servers (concurrent requests).
- **`client_single.py`** — sequential client for the single‑threaded server.

### Docker files
- **`server.dockerfile`**
- **`client.dockerfile`** (can be reused for both clients if desired)
- **`docker-compose.yml`** — defines three server services and three clients.

```
lab2/
├─ server.dockerfile
├─ client.dockerfile
├─ docker-compose.yml
├─ singlethreaded_server.py
├─ multithreaded_server_no_lock.py
├─ multithreaded_server_lock.py
├─ client.py
├─ client_single.py
├─ public/                 # optional static assets to serve
└─ screenshots/            # figures used in this report
```

![directories.png](screenshots/directories.png)

---

## 3. Docker Containerization

### `client.dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY client.py .
COPY client_single.py .
RUN pip install requests
CMD ["python", "client.py"]
```

### `server.dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY multithreaded_server_lock.py .
COPY multithreaded_server_no_lock.py .
COPY singlethreaded_server.py .
COPY public/ ./public/
EXPOSE 8000 8001 8002
CMD ["python", "singlethreaded_server.py"]
```

### `docker-compose.yml`
```yaml
services:
  singlethreaded-server:
    build:
      context: .
      dockerfile: server.dockerfile
    container_name: singlethreaded-server
    ports:
      - "8000:8000"
    command: ["python", "singlethreaded_server.py"]
    networks: [app-network]

  multithreaded-lock-server:
    build:
      context: .
      dockerfile: server.dockerfile
    container_name: multithreaded-lock-server
    ports:
      - "8001:8001"
    command: ["python", "multithreaded_server_lock.py"]
    networks: [app-network]

  multithreaded-nolock-server:
    build:
      context: .
      dockerfile: server.dockerfile
    container_name: multithreaded-nolock-server
    ports:
      - "8002:8002"
    command: ["python", "multithreaded_server_no_lock.py"]
    networks: [app-network]

  client-single:
    build:
      context: .
      dockerfile: client.dockerfile
    container_name: client-single
    depends_on: [singlethreaded-server]
    environment:
      SERVER_HOST: singlethreaded-server
      SERVER_PORT: "8000"
    command: ["python", "client_single.py"]
    networks: [app-network]

  client-lock:
    build:
      context: .
      dockerfile: client.dockerfile
    container_name: client-lock
    depends_on: [multithreaded-lock-server]
    environment:
      SERVER_HOST: multithreaded-lock-server
      SERVER_PORT: "8001"
    command: ["python", "client.py"]
    networks: [app-network]

  client-nolock:
    build:
      context: .
      dockerfile: client.dockerfile
    container_name: client-nolock
    depends_on: [multithreaded-nolock-server]
    environment:
      SERVER_HOST: multithreaded-nolock-server
      SERVER_PORT: "8002"
    command: ["python", "client.py"]
    networks: [app-network]

networks:
  app-network:
    driver: bridge
```

---

## 4. Starting the Containers

The following commands will:
1) Build all images  
2) Run a server container  
3) Run a client container

```bash
docker compose build
docker compose up singlethreaded-server
# in another terminal
docker compose run client-single
```

For the multithreaded scenarios, use:
```bash
# With locks
docker compose up multithreaded-lock-server
docker compose run client-lock

# Without locks
docker compose up multithreaded-nolock-server
docker compose run client-nolock
```

**Screenshots:**  
![compose_build.png](screenshots/compose_build.png)  
![up_single.png](screenshots/up_single.png)

---

## 5. Demonstrations & Results

### Case 1 — Single‑threaded server
1. Start server:
   ```bash
   docker compose up singlethreaded-server
   ```
2. Run client:
   ```bash
   docker compose run client-single
   ```

The client sends **10 requests** of ~1s each; server processes them **sequentially**.  
**Measured total time** ≈ **10–11 s** (e.g., 10.13 s).

Screens:
- Server run: ![up_single.png](screenshots/up_single.png)  
- Client output: ![client_single.png](screenshots/client_single.png)

***

### Case 2 — Multithreaded server **without** lock (race condition)
1. Start server:
   ```bash
   docker compose up multithreaded-nolock-server
   ```
2. Run client:
   ```bash
   docker compose run client-nolock
   ```

The client issues **10 concurrent requests**. The server enforces **RATE_LIMIT = 5** req/s but **no lock** is used.  
With a tiny intentional delay (e.g., `time.sleep(0.01)`) near the shared counter, a **race condition** appears: some seconds record **<5** or **>5** accepted requests.

Screens:
- Server run: ![up_multi_nolock.png](screenshots/up_multi_nolock.png)  
- Client output: ![client_nolock.png](screenshots/client_nolock.png)  
- Race visualization: ![race_cond.png](screenshots/race_cond.png)

***

### Case 3 — Multithreaded server **with** lock (fixed)
1. Start server:
   ```bash
   docker compose up multithreaded-lock-server
   ```
2. Run client:
   ```bash
   docker compose run client-lock
   ```

A **thread lock** protects the shared state (request counters & rate‑limit windows).  
Result: each second **exactly 5** requests are admitted; no anomalies.

Screens:
- Server run: ![up_lock_server.png](screenshots/up_lock_server.png)  
- Client output: ![client_lock.png](screenshots/client_lock.png)  
- Fixed race view: ![race_cond_no.png](screenshots/race_cond_no.png)

---

## 6. Rate Limiting (Design Snapshot)

**Data structures:**
```python
from collections import defaultdict
import threading

RATE_LIMIT = 5  # requests / second
rate_limit_dict = defaultdict(list)   # ip -> [timestamps]
rate_lock = threading.Lock()
```

**Check & enforce in handler:**
```python
with rate_lock:
    now = time.time()
    timestamps = [t for t in rate_limit_dict[client_ip] if now - t < 1]
    if len(timestamps) >= RATE_LIMIT:
        self.send_response(429); self.end_headers()
        self.wfile.write(b"Rate limit exceeded\n")
        return
    timestamps.append(now)
    rate_limit_dict[client_ip] = timestamps
```

---

## 7. Thread Locks (Why & How)

A **Lock** is a synchronization primitive for **exclusive access** to shared state. When one thread acquires the lock, others must wait until it’s released. This prevents interleavings that cause **race conditions**.

**Example usage in the locked server:**
```python
request_counter = defaultdict(int)
counter_lock = threading.Lock()

# Increment safely
with counter_lock:
    request_counter[self.path] += 1
```

Combined with the **rate_lock** above, the server eliminates races both in **rate limiting** and **per‑path counting**.

---

## 8. Timing Comparison (example)

- **Single‑threaded (10 × 1s):** ~10–11 s total
- **Multithreaded without lock:** shows anomalies in per‑second admitted counts (race)
- **Multithreaded with lock:** correct per‑second admitted counts; total wall‑time reduced due to concurrency but capped by rate limit

(Insert your measured numbers and graphs here.)  
![timings.png](screenshots/timings.png)

---

## 9. Conclusions

- Multithreading improves **throughput** and **wall‑clock time** for multiple requests, but **unsynchronized shared state** leads to **races** and broken invariants.
- Using **thread locks** restores correctness under concurrency, at a small coordination cost.
- Rate limiting with shared buckets requires **atomic updates** (lock or other concurrency‑safe approach).
- The experiment highlights the trade‑offs between **performance** and **synchronization overhead**.

---

## 10. Repro Instructions (TA Quick Start)

```bash
cd lab2
docker compose build

# Single-threaded demo
docker compose up singlethreaded-server
# new terminal:
docker compose run client-single

# MT without lock
docker compose up multithreaded-nolock-server
# new terminal:
docker compose run client-nolock

# MT with lock
docker compose up multithreaded-lock-server
# new terminal:
docker compose run client-lock
```


<!-- ## Lab 2: Concurrent HTTP Server (on top of Lab 1)

This keeps the Lab 1 TCP-socket server shape, adds:
- **Concurrency**: `single`, `threaded` (thread-per-request), or bounded `pool`.
- **Artificial delay** to expose concurrency (~1s).
- **Per-file counters** shown in directory listings.
  - `COUNTER_MODE=naive` intentionally racy (read-modify-write with small sleep).
  - `COUNTER_MODE=locked` fixes the race with a mutex.
- **Per-IP rate limiting** ~5 rps using a token bucket (HTTP 429 on exceed).

### Run locally

```bash
# baseline single-threaded (expect ~10s for 10 concurrent reqs)
PORT=8080 THREADING_MODE=single HANDLER_DELAY_MS=1000 python server.py

# concurrent thread-per-request (~1-2s for 10 concurrent reqs)
THREADING_MODE=threaded HANDLER_DELAY_MS=1000 python server.py

# fixed thread pool of 8 (~2s for 10 concurrent reqs)
THREADING_MODE=pool POOL_SIZE=8 HANDLER_DELAY_MS=1000 python server.py

```

## Folder structure
```
pr-lab2/
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

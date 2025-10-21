## Lab 2: Concurrent HTTP Server (on top of Lab 1)

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
```

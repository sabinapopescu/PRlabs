# Lab 2 — Concurrent HTTP Server (Multithreading, Race Condition, Rate Limiting)

**Author:** Popescu Sabina (FAF‑233)

> All experiments use **your Lab‑2 server** (`server.py`) on **http://localhost:8082** (container: `pr-lab2-web`).  
> Configuration is via `lab2/docker-compose.yml` environment variables:
> `THREADING_MODE` = `single`/`threaded`/`pool`, `POOL_SIZE`, `HANDLER_DELAY_MS`,  
> `COUNTER_MODE` = `naive`/`locked`, `RATE_LIMIT_RPS`, `RATE_LIMIT_BURST`.

---

## 0) How to (re)start between scenarios

```bash
cd lab2
docker compose down
docker compose up -d --build
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep pr-lab2-web
# Use GET for header checks (server only implements GET):
curl -s -D- http://localhost:8082/ -o /dev/null
```

---

## 1) Performance comparison between the two servers

Each request simulates ~`HANDLER_DELAY_MS = 1000 ms`. We send **10 requests** in parallel and measure wall‑time.

### 1.a) Single‑threaded server (baseline)

**Compose env:**
```yaml
THREADING_MODE: "single"
HANDLER_DELAY_MS: "1000"
```

**Run & measure (10 parallel GETs):**
```bash
cd lab2 && docker compose up -d --build
time seq 10 | xargs -n1 -P10 -I{} curl -s -o /dev/null http://localhost:8082/image.png
```

- **Measured time (paste `real`):** `____ s`  
- 📸 `screenshots/perf_single_10req.png`

---

### 1.b) Multi‑threaded server

Pick one (you can do both):  
**Thread-per-request**
```yaml
THREADING_MODE: "threaded"
HANDLER_DELAY_MS: "1000"
```
**OR Fixed pool**
```yaml
THREADING_MODE: "pool"
POOL_SIZE: "8"
HANDLER_DELAY_MS: "1000"
```

**Run & measure:**
```bash
docker compose up -d --build
time seq 10 | xargs -n1 -P10 -I{} curl -s -o /dev/null http://localhost:8082/image.png
```

- **Measured time (paste `real`):** `____ s`  
- 📸 `screenshots/perf_multi_10req.png`

**Expected shape:** single ≈ 10–11s; threaded/pool ≈ 1–3s for 10×1s with concurrency 8–10.

---

## 2) Hit counter & race condition

Your server exposes a per‑file counter shown in the directory listing.

### 2.a) Trigger a race

**Compose env:**
```yaml
THREADING_MODE: "threaded"   # or "pool"
COUNTER_MODE: "naive"
```

**Hammer the same file; then read the count from listing:**
```bash
docker compose up -d --build
seq 100 | xargs -n1 -P20 -I{} curl -s -o /dev/null http://localhost:8082/image.png
curl -s http://localhost:8082/ | grep -E 'image\.png|requests'
```
- **Observation:** `requests: N` is **< 100** (lost updates).  
- 📸 `screenshots/race_naive.png`

### 2.b) Code responsible (≤ 4 lines)

```python
# NAIVE (racy): read-modify-write without a lock
old = request_counts[full_path]
time.sleep(0.002)
request_counts[full_path] = old + 1
```

### 2.c) Fixed code (≤ 4 lines)

```python
# FIXED (mutex-protected)
with counts_lock:
    request_counts[full_path] += 1
```

**Verify after fix:**
```yaml
COUNTER_MODE: "locked"
```
```bash
docker compose up -d --build
seq 100 | xargs -n1 -P20 -I{} curl -s -o /dev/null http://localhost:8082/image.png
curl -s http://localhost:8082/ | grep -E 'image\.png|requests'
```
- **Observation:** count matches the number of hits (no losses).  
- 📸 `screenshots/race_locked.png`

---

## 3) Rate limiting

Server uses a **per‑IP token bucket** (env: `RATE_LIMIT_RPS`, `RATE_LIMIT_BURST`).

### 3.a) Show how you spam requests (specify Requests/second)

**Burst (very high R/s):**
```bash
seq 40 | xargs -n1 -P30 -I{} curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8082/ \
  | sort | uniq -c
# ≈30 req/s for a short burst with -P30
```
**Controlled ~10 R/s for ~10s (100 req):**
```bash
for i in $(seq 100); do
  (curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8082/ &)
  sleep 0.10
done; wait
```
- 📸 `screenshots/ratelimit_spam.png` (show the command + comment the intended R/s).

### 3.b) Response statistics (successful R/s, denied R/s)

```bash
start=$(date +%s)
seq 100 | xargs -n1 -P40 -I{} \
  curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8082/ \
  | tee /tmp/codes.txt >/dev/null
end=$(date +%s); dur=$(( end - start )); [ $dur -eq 0 ] && dur=1
ok=$(grep -c '^200$' /tmp/codes.txt || true)
deny=$(grep -c '^429$' /tmp/codes.txt || true)
printf "Duration: %ss  200/s: %.2f  429/s: %.2f\n" "$dur" "$(echo "$ok/$dur" | bc -l)" "$(echo "$deny/$dur" | bc -l)"
```
- 📸 `screenshots/ratelimit_rates.png` (include duration + computed 200/s and 429/s).

### 3.c) Per‑IP awareness (second IP still succeeds)

Run a second client in another container on the same Compose network (`lab2_default`).

```bash
# Host keeps spamming at high concurrency
seq 40 | xargs -n1 -P30 -I{} curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8082/ | sort | uniq -c

# Second IP from a container:
docker run --rm --network lab2_default curlimages/curl:8.10.1 \
  sh -c "seq 20 | xargs -n1 -P20 -I{} curl -s -o /dev/null -w '%{http_code}\n' http://pr-lab2-web:8080/ | sort | uniq -c"
```
- **Expected:** while the host sees many `429`, the container still gets mostly `200`.  
- 📸 `screenshots/ratelimit_host.png` + `screenshots/ratelimit_container.png`

---

## 4) Brief design notes (context to screenshots)

- **Threading modes:** `single` (serial), `threaded` (per‑request), `pool` (fixed workers + queue).
- **Artificial delay:** `HANDLER_DELAY_MS` makes concurrency effects visible.
- **Race demo:** `COUNTER_MODE=naive` uses read‑modify‑write with a tiny sleep; `locked` uses a mutex.
- **Rate limiting:** token bucket per client IP (thread‑safe via an internal lock).

---

## 5) What to submit (screenshot checklist)

- `perf_single_10req.png` — time for 10 parallel requests (single‑threaded)
- `perf_multi_10req.png` — time for 10 parallel requests (multi‑threaded or pool)
- `race_naive.png` — listing showing lost counts with `COUNTER_MODE=naive`
- `race_locked.png` — listing showing correct counts with `COUNTER_MODE=locked`
- `ratelimit_spam.png` — the spam command(s) + stated R/s
- `ratelimit_rates.png` — computed 200/s and 429/s
- `ratelimit_host.png` & `ratelimit_container.png` — per‑IP demonstration

---

## 6) Conclusions

- Concurrency reduces wall‑time significantly compared to a serial server under 1s/request load.
- Unsynchronized increments lose updates; a **mutex** fixes the race deterministically.
- **Token‑bucket** rate limiting protects the server and is **per‑IP**, so one client cannot starve others.

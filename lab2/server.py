#!/usr/bin/env python3
# server.py — Lab 2: Concurrent HTTP server on top of Lab 1 (TCP sockets)
# Modes: single-threaded, thread-per-request, or fixed thread pool.
# Features: artificial delay, per-file request counter (race vs locked), per-IP rate limiting.

import os, socket, threading, time, queue, mimetypes, urllib.parse
from collections import defaultdict

# ----------------- Configuration via env -----------------
PORT               = int(os.getenv("PORT", "8080"))
CONTENT_ROOT       = os.getenv("CONTENT_ROOT", "content")
THREADING_MODE     = os.getenv("THREADING_MODE", "threaded")  # single|threaded|pool
POOL_SIZE          = int(os.getenv("POOL_SIZE", "8"))
HANDLER_DELAY_MS   = int(os.getenv("HANDLER_DELAY_MS", "1000"))
COUNTER_MODE       = os.getenv("COUNTER_MODE", "locked")      # naive|locked
RATE_LIMIT_RPS     = float(os.getenv("RATE_LIMIT_RPS", "5"))
RATE_LIMIT_BURST   = float(os.getenv("RATE_LIMIT_BURST", "5"))

os.makedirs(CONTENT_ROOT, exist_ok=True)
mimetypes.init()

# ----------------- Global state -----------------
request_counts = defaultdict(int)
counts_lock    = threading.Lock()  # used only in locked mode

# Token-bucket rate limiter per IP (thread-safe)
class TokenBucket:
    def __init__(self, rate, burst):
        self.rate = rate
        self.capacity = burst
        self.tokens = burst
        self.timestamp = time.monotonic()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            # refill based on elapsed time
            self.tokens = min(self.capacity, self.tokens + (now - self.timestamp) * self.rate)
            self.timestamp = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

buckets = {}
buckets_lock = threading.Lock()

def limiter_for(ip: str) -> TokenBucket:
    with buckets_lock:
        tb = buckets.get(ip)
        if tb is None:
            tb = TokenBucket(RATE_LIMIT_RPS, RATE_LIMIT_BURST)
            buckets[ip] = tb
        return tb

# ----------------- Helpers -----------------
def http_response(conn, status_code, reason, headers=None, body=b""):
    if headers is None: headers = {}
    headers.setdefault("Content-Length", str(len(body)))
    headers.setdefault("Connection", "close")
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
    head = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    conn.sendall(status_line.encode() + head.encode() + b"\r\n" + body)

def normalize_path(url_path: str) -> str:
    # URL-decode, strip query/fragment, prevent directory traversal
    path = urllib.parse.urlparse(url_path).path
    path = urllib.parse.unquote(path)
    if path.startswith("/"): path = path[1:]
    # no .. traversal
    safe = os.path.normpath(path)
    if safe.startswith(".."): safe = ""
    abs_path = os.path.join(CONTENT_ROOT, safe)
    return abs_path

def list_dir_html(abs_dir: str) -> bytes:
    items = []
    names = sorted(os.listdir(abs_dir))
    for name in names:
        full = os.path.join(abs_dir, name)
        if os.path.isdir(full):
            items.append(f'<li>[DIR] <a href="{name}/">{name}/</a></li>')
        else:
            cnt = request_counts[full] if COUNTER_MODE == "naive" else (counts_locked_read(full))
            items.append(f'<li><a href="{name}">{name}</a> — requests: {cnt}</li>')
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Index of /</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; padding:24px}}
h1{{margin:0 0 12px}} ul{{line-height:1.8}}</style></head>
<body><h1>Index of {abs_dir.removeprefix(CONTENT_ROOT)}</h1>
<ul>
{''.join(items)}
</ul>
</body></html>"""
    return html.encode()

def counts_locked_read(full_path: str) -> int:
    with counts_lock:
        return request_counts[full_path]

def increment_counter(full_path: str):
    if not os.path.isfile(full_path):
        return
    if COUNTER_MODE == "naive":
        # *** Intentionally racy: read-modify-write with a tiny delay to widen the race window
        old = request_counts[full_path]
        time.sleep(0.002)
        request_counts[full_path] = old + 1
    else:
        # *** Correct: atomic increment under a mutex
        with counts_lock:
            request_counts[full_path] += 1

def serve_file(conn, abs_path):
    # Content-Type
    ctype = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
    try:
        size = os.path.getsize(abs_path)
        headers = {"Content-Type": ctype, "Content-Length": str(size)}
        conn.sendall(f"HTTP/1.1 200 OK\r\n".encode())
        conn.sendall("".join(f"{k}: {v}\r\n" for k,v in headers.items()).encode())
        conn.sendall(b"\r\n")
        with open(abs_path, "rb") as f:
            # stream in chunks
            while True:
                data = f.read(64*1024)
                if not data: break
                conn.sendall(data)
    except OSError:
        http_response(conn, 404, "Not Found", {"Content-Type": "text/plain"}, b"Not Found\n")

# ----------------- Request handler -----------------
def handle_connection(conn: socket.socket, addr):
    client_ip, client_port = addr[0], addr[1]
    try:
        # basic HTTP request parsing (single request per connection)
        data = b""
        conn.settimeout(5)
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
            if len(data) > 65536: break

        # First line: METHOD PATH HTTP/1.1
        try:
            head = data.split(b"\r\n\r\n", 1)[0].decode(errors="ignore")
            request_line = head.split("\r\n")[0]
            method, url_path, _ = request_line.split(" ")
        except Exception:
            http_response(conn, 400, "Bad Request", {"Content-Type": "text/plain"}, b"Bad Request\n")
            return

        # Rate limiting per IP
        tb = limiter_for(client_ip)
        if not tb.allow():
            http_response(conn, 429, "Too Many Requests",
                          {"Retry-After": "1", "Content-Type": "text/plain"},
                          b"Too Many Requests\n")
            return

        # Artificial handler delay to expose concurrency in measurements
        if HANDLER_DELAY_MS > 0:
            time.sleep(HANDLER_DELAY_MS / 1000.0)

        abs_path = normalize_path(url_path)

        if method != "GET":
            http_response(conn, 405, "Method Not Allowed",
                          {"Allow": "GET", "Content-Type": "text/plain"},
                          b"Method Not Allowed\n")
            return

        # Directory?
        if os.path.isdir(abs_path):
            # If a trailing slash is missing for directories, we could redirect; keep it simple.
            body = list_dir_html(abs_path)
            http_response(conn, 200, "OK", {"Content-Type": "text/html; charset=utf-8"}, body)
            return

        # File?
        if os.path.isfile(abs_path):
            increment_counter(abs_path)
            serve_file(conn, abs_path)
            return

        # Not found
        http_response(conn, 404, "Not Found", {"Content-Type": "text/plain"}, b"Not Found\n")

    except socket.timeout:
        # Close silently on timeout
        pass
    except Exception as e:
        # Minimal 500 on unexpected errors
        body = f"Internal Server Error\n{e}\n".encode()
        http_response(conn, 500, "Internal Server Error", {"Content-Type": "text/plain"}, body)
    finally:
        try: conn.shutdown(socket.SHUT_RDWR)
        except: pass
        conn.close()

# ----------------- Server skeletons -----------------
def run_single():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", PORT))
        s.listen(128)
        print(f"[single] Serving on http://0.0.0.0:{PORT}  root={CONTENT_ROOT}")
        while True:
            conn, addr = s.accept()
            handle_connection(conn, addr)

def run_threaded():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", PORT))
        s.listen(128)
        print(f"[threaded] Serving on http://0.0.0.0:{PORT}  root={CONTENT_ROOT}")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_connection, args=(conn, addr), daemon=True)
            t.start()

def run_pool():
    taskq = queue.Queue()

    def worker():
        while True:
            conn, addr = taskq.get()
            try:
                handle_connection(conn, addr)
            finally:
                taskq.task_done()

    workers = [threading.Thread(target=worker, daemon=True) for _ in range(POOL_SIZE)]
    for t in workers: t.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", PORT))
        s.listen(128)
        print(f"[pool:{POOL_SIZE}] Serving on http://0.0.0.0:{PORT}  root={CONTENT_ROOT}")
        while True:
            conn, addr = s.accept()
            taskq.put((conn, addr))

if __name__ == "__main__":
    mode = THREADING_MODE.lower()
    print(f"CONFIG  mode={mode} pool={POOL_SIZE} delay_ms={HANDLER_DELAY_MS} "
          f"counter={COUNTER_MODE} rps={RATE_LIMIT_RPS} burst={RATE_LIMIT_BURST}")
    if mode == "single":
        run_single()
    elif mode == "pool":
        run_pool()
    else:
        run_threaded()

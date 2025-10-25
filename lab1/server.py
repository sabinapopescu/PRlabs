#!/usr/bin/env python3
"""Minimal single-connection HTTP file server for Lab 1 (GET + HEAD)."""

import argparse
import datetime
import os
import socket
import urllib.parse
from typing import Optional

CRLF = b"\r\n"

# Only what you use (+ .ico to quiet favicon probes)
MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".png":  "image/png",
    ".pdf":  "application/pdf",
    ".ico":  "image/x-icon",
}

def http_date_now() -> str:
    """Return current time formatted for HTTP headers (GMT)."""
    # Avoid deprecated utcnow()
    return datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

def build_response(status_code: int, reason: str, headers: Optional[dict] = None,
                   body: bytes = b"", *, content_length_override: Optional[int] = None) -> bytes:
    """Build an HTTP/1.1 response with common headers."""
    lines = [f"HTTP/1.1 {status_code} {reason}"]
    base_headers = {
        "Server": "MinimalPySocketServer/1.1",
        "Date": http_date_now(),
        "Connection": "close",
        "Content-Length": str(content_length_override if content_length_override is not None else len(body)),
    }
    if headers:
        base_headers.update(headers)
    for k, v in base_headers.items():
        lines.append(f"{k}: {v}")
    head = (("\r\n").join(lines) + "\r\n\r\n").encode("utf-8")
    return head + body

def safe_join(root: str, url_path: str) -> Optional[str]:
    """Resolve URL path to a filesystem path under root; strip ?query/#fragment."""
    path_only = url_path.split("?", 1)[0].split("#", 1)[0]
    decoded = urllib.parse.unquote(path_only)
    fs_path = os.path.realpath(os.path.join(root, decoded.lstrip("/")))
    root_real = os.path.realpath(root)
    if not fs_path.startswith(root_real):
        return None
    return fs_path

def guess_mime(path: str) -> Optional[str]:
    """Return MIME type for allowed extensions, else None (strict)."""
    _, ext = os.path.splitext(path.lower())
    return MIME_MAP.get(ext)

def make_dir_listing_html(url_path: str, abs_dir_path: str) -> bytes:
    """Generate a simple directory listing HTML."""
    items = []
    if url_path != "/":
        parent = os.path.dirname(url_path.rstrip("/")) or "/"
        items.append(f'<li><a href="{parent}">.. (parent)</a></li>')
    for name in sorted(os.listdir(abs_dir_path)):
        full = os.path.join(abs_dir_path, name)
        display = name + ("/" if os.path.isdir(full) else "")
        href = urllib.parse.urljoin(url_path.rstrip("/") + "/", name)
        items.append(f'<li><a href="{href}">{display}</a></li>')
    body = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Index of {url_path}</title></head>
<body>
  <h1>Index of {url_path}</h1>
  <ul>
    {''.join(items)}
  </ul>
</body>
</html>"""
    return body.encode("utf-8")

def handle_client(conn: socket.socket, _addr, root: str) -> None:
    """Read one HTTP request from client socket and send a response."""
    data = b""
    conn.settimeout(2.0)
    try:
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass

    if not data:
        conn.sendall(build_response(400, "Bad Request", body=b""))
        return

    try:
        header_text = data.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1")
        request_line = header_text.split("\r\n", 1)[0]
        parts = request_line.split(" ")
        if len(parts) < 3:
            raise ValueError("malformed request line")
        method, path = parts[0].upper(), parts[1]
    except (UnicodeDecodeError, ValueError):
        conn.sendall(build_response(400, "Bad Request", body=b""))
        return

    # Accept GET and HEAD (HEAD = headers + Content-Length, no body)
    if method not in ("GET", "HEAD"):
        conn.sendall(build_response(405, "Method Not Allowed", headers={"Allow": "GET, HEAD"}, body=b""))
        return

    fs_path = safe_join(root, path)
    if fs_path is None:
        conn.sendall(build_response(403, "Forbidden", body=b""))
        return

    # Directory: list contents
    if os.path.isdir(fs_path):
        listing = make_dir_listing_html(path, fs_path)
        if method == "HEAD":
            conn.sendall(build_response(200, "OK",
                                        headers={"Content-Type": "text/html; charset=utf-8"},
                                        body=b"", content_length_override=len(listing)))
        else:
            conn.sendall(build_response(200, "OK",
                                        headers={"Content-Type": "text/html; charset=utf-8"},
                                        body=listing))
        return

    # Regular file
    if os.path.isfile(fs_path):
        mime = guess_mime(fs_path)
        if not mime:  # strict: only whitelisted types
            conn.sendall(build_response(404, "Not Found", body=b""))
            return
        if method == "HEAD":
            size = os.path.getsize(fs_path)
            conn.sendall(build_response(200, "OK",
                                        headers={"Content-Type": mime},
                                        body=b"", content_length_override=size))
            return
        try:
            with open(fs_path, "rb") as f:
                body = f.read()
        except OSError:
            conn.sendall(build_response(500, "Internal Server Error", body=b""))
            return
        conn.sendall(build_response(200, "OK", headers={"Content-Type": mime}, body=body))
        return

    conn.sendall(build_response(404, "Not Found", body=b""))

def run_server(root_dir: str, host: str, port: int) -> None:
    """Start the single-connection HTTP server bound to host:port."""
    print(f"[INFO] Serving '{root_dir}' at http://{host}:{port} (one request at a time)")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(5)
        while True:
            conn, addr = s.accept()
            with conn:
                handle_client(conn, addr, root_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal HTTP file server (single-connection).")
    parser.add_argument("root", help="Directory to serve")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        raise SystemExit(f"Error: directory not found: {args.root}")

    run_server(args.root, args.host, args.port)

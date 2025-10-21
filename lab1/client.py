#!/usr/bin/env python3
import os, sys, socket

CRLF = "\r\n"

def parse_headers(raw_headers: bytes):
    lines = raw_headers.decode("iso-8859-1").split("\r\n")
    status_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status_line, headers

def main():
    if len(sys.argv) != 5:
        print("Usage: client.py server_host server_port url_path directory")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    path = sys.argv[3] if sys.argv[3].startswith("/") else "/" + sys.argv[3]
    out_dir = sys.argv[4]
    os.makedirs(out_dir, exist_ok=True)

    req = (
        f"GET {path} HTTP/1.1{CRLF}"
        f"Host: {host}:{port}{CRLF}"
        f"Connection: close{CRLF}"
        f"User-Agent: MinimalPyClient/1.0{CRLF}{CRLF}"
    ).encode("utf-8")

    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(req)
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    resp = b"".join(chunks)

    if b"\r\n\r\n" not in resp:
        print("[ERROR] Invalid HTTP response")
        sys.exit(2)

    header_bytes, body = resp.split(b"\r\n\r\n", 1)
    status_line, headers = parse_headers(header_bytes)

    print(status_line)

    ctype = headers.get("content-type", "")
    if ctype.startswith("text/html"):
        try:
            print(body.decode("utf-8", errors="replace"))
        except Exception:
            print(body.decode("iso-8859-1", errors="replace"))
    elif ctype.startswith("image/png") or ctype.startswith("application/pdf"):
        name = os.path.basename(path.rstrip("/")) or "index"
        if ctype.startswith("image/png") and not name.endswith(".png"):
            name += ".png"
        if ctype.startswith("application/pdf") and not name.endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        with open(out_path, "wb") as f:
            f.write(body)
        print(f"[SAVED] {out_path}")
    else:
        print(body.decode("utf-8", errors="replace"))

if __name__ == "__main__":
    main()

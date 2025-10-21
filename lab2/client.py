#!/usr/bin/env python3
# client.py — spawn N concurrent GETs and measure elapsed wall time and throughput
import http.client, threading, time, argparse

def hit(host, port, path, out, idx):
    try:
        c = http.client.HTTPConnection(host, port, timeout=10)
        c.request("GET", path)
        r = c.getresponse()
        r.read()  # drain
        out[idx] = r.status
        c.close()
    except Exception:
        out[idx] = -1

def run(host="127.0.0.1", port=8080, path="/index.html", concurrency=10):
    results = [-2] * concurrency
    threads = [threading.Thread(target=hit, args=(host, port, path, results, i)) for i in range(concurrency)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    dt = time.perf_counter() - t0
    ok = sum(1 for s in results if s == 200)
    by_code = {}
    for s in results: by_code[s] = by_code.get(s, 0) + 1
    print(f"Elapsed: {dt:.3f}s | OK: {ok}/{concurrency} | Throughput: {ok/dt:.2f} successful req/s")
    print("Status counts:", by_code)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--path", default="/index.html")
    ap.add_argument("-c", "--concurrency", type=int, default=10)
    args = ap.parse_args()
    run(args.host, args.port, args.path, args.concurrency)

import argparse
import sys
import time
import urllib.error
import urllib.request
import threading
import socket
from typing import Dict, Any, List


def http_request(idx: int, url: str, timeout: float, results: List[Dict[str, Any]],
               results_lock: threading.Lock, quiet: bool) -> None:
    start = time.perf_counter()
    status = None
    size = 0
    error = None
    success = False

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            data = resp.read()
            size = len(data) if data is not None else 0
            success = 200 <= (status or 0) < 400
    except urllib.error.HTTPError as e:
        status = e.code
        error = f"HTTPError: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        error = f"URLError: {e.reason}"
    except Exception as e:
        error = f"Error: {e}"
    finally:
        elapsed = time.perf_counter() - start

    result = {
        "index": idx,
        "success": success,
        "status": status,
        "elapsed": elapsed,
        "bytes": size,
        "error": error,
    }

    with results_lock:
        results.append(result)
        if not quiet:
            status_str = f"[{result['status']}]" if result['status'] else "[FAIL]"
            if result["success"]:
                print(f"~ {idx:3d}  {status_str:<6} {result['elapsed'] * 1000:8.2f} ms     {result['bytes']:5d} B")
            else:
                print(
                    f"~ {idx:3d}  {status_str:<6} {result['elapsed'] * 1000:8.2f} ms     ERROR: {result['error'] or 'Unknown'}")


def init_run(url: str, requests: int, timeout: float, quiet: bool, delay: float = 0.0) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    results_lock = threading.Lock()
    threads = []
    total_start = time.perf_counter()

    for i in range(1, requests + 1):
        thread = threading.Thread(
            target=http_request,
            args=(i, url, timeout, results, results_lock, quiet),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        if delay > 0 and i < requests:
            time.sleep(delay)

    for thread in threads:
        thread.join()

    total_elapsed = time.perf_counter() - total_start
    return {"results": results, "total_elapsed": total_elapsed}


def stats(results: List[Dict[str, Any]], total_elapsed: float, url: str) -> None:
    successes = sum(1 for r in results if r["success"])
    throughput = successes / total_elapsed if total_elapsed > 0 else float("inf")

    try:
        requester_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        requester_ip = "unknown"

    print("\n" + "~" * 97)
    print("STATS:")
    print("~" * 97)
    print(f"Server:           {url}")
    print(f"Requester:        {requester_ip}")
    print(f"Successful:       {successes}/{len(results)}")
    print(f"Total time:       {total_elapsed:.3f} s")
    print(f"Throughput:       {throughput:.2f} req/s")
    print("~" * 97)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent HTTP load client")
    parser.add_argument("-H", "--host", required=True)
    parser.add_argument("-p", "--port", type=int, required=True)
    parser.add_argument("-u", "--url", required=True)
    parser.add_argument("-r", "--requests", type=int, required=True)
    parser.add_argument("-t", "--time", type=float, default=0.0)
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if args.requests <= 0:
        print("Error: requests must be > 0", file=sys.stderr)
        return 2

    url = f"http://{args.host}:{args.port}{args.url}"

    if args.time > 0 and args.requests > 1:
        delay = args.time / (args.requests - 1)
    else:
        delay = 0.0

    timeout = 10.0
    quiet = False

    print("\n" + "~" * 97)
    print(f"Requests:     {args.requests:<5}")
    print(f"Duration:     {args.time:.1f}s")
    print(f"Delay: {delay:.3f}s\n")

    run_result = init_run(url, args.requests, timeout, quiet, delay)
    stats(run_result["results"], run_result["total_elapsed"], url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

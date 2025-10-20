import argparse
import threading
import time
import urllib.request
import urllib.error

def normalize_path(path):
    segments = [seg for seg in path.split('/') if seg]

    normalized_segments = []
    for segment in segments:
        if len(segment) >= 3 and segment == '.' * len(segment):
            continue
        normalized_segments.append(segment)

    return '/' + '/'.join(normalized_segments)


def http_request(url, request_id, results, lock):
    start_time = time.time()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            _ = response.read()
            duration = time.time() - start_time
            status = response.status
            result = (request_id, duration, True, f"HTTP {status}")
    except urllib.error.HTTPError as e:
        duration = time.time() - start_time
        result = (request_id, duration, False, f"HTTP {e.code}")
    except urllib.error.URLError as e:
        duration = time.time() - start_time
        result = (request_id, duration, False, f"URL Error: {e.reason}")
    except Exception as e:
        duration = time.time() - start_time
        result = (request_id, duration, False, f"Error: {str(e)}")

    with lock:
        results.append(result)


def init_run_threads(url, num_requests, results, sync_lock):
    threads = []

    start_time = time.time()

    for i in range(1, num_requests + 1):
        thread = threading.Thread(
            target=http_request,
            args=(url, i, results, sync_lock),
            daemon=True
        )
        threads.append(thread)
        thread.start()

    return threads, start_time


def wait_for_all_threads(threads, start_time):
    for thread in threads:
        thread.join()

    return time.time() - start_time


def calculate_statistics(results, duration, num_requests):
    successful_requests = [r for r in results if r[2]]
    failed_requests = [r for r in results if not r[2]]

    requests_per_second = len(successful_requests) / duration if duration > 0 else 0

    return {
        'successful': successful_requests,
        'failed': failed_requests,
        'requests_per_second': requests_per_second,
        'overall_duration': duration,
        'num_requests': num_requests
    }


def print_results_summary(stats):
    print(f"\nSTATISTICS:")
    print(f"Taken:              {stats['overall_duration']:.3f}s")
    print(f"Reqs:               {stats['num_requests']}")
    print(f"Successful reqs:    {len(stats['successful'])}")
    print(f"Failed reqs:        {len(stats['failed'])}")
    print(f"Success rate:       {len(stats['successful']) / stats['num_requests'] * 100:.1f}%")
    print(f"Overall:            {stats['requests_per_second']:.2f}reqs/s")


def print_failed_requests(failed_requests):
    if failed_requests:
        print(f"\nFAILED REQUESTS:")
        for req_id, duration, success, status in failed_requests:
            print(f"  Request {req_id}: {status} ({duration:.3f}s)")


def exec_concurrent_test(url, num_requests):
    print(f"\nTesting: {url}")
    print(f"Requests: {num_requests}")
    print("~" * 69)

    results = []
    sync_lock = threading.Lock()

    threads, start_time = init_run_threads(url, num_requests, results, sync_lock)

    duration = wait_for_all_threads(threads, start_time)

    stats = calculate_statistics(results, duration, num_requests)

    print_results_summary(stats)
    print_failed_requests(stats['failed'])

    print("~" * 69)


def main():
    parser = argparse.ArgumentParser(description="Concurrent HTTP Request Tester")
    parser.add_argument("-u", "--url", default="/",
                        help="URL path to request (default: /)")
    parser.add_argument("-r", "--requests", type=int, default=10,
                        help="Number of concurrent requests (default: 10)")
    parser.add_argument("-H", "--host", default="localhost",
                        help="Server host (default: localhost)")
    parser.add_argument("-p", "--port", type=int, default=1337,
                        help="Server port (default: 1337)")

    args = parser.parse_args()

    if args.requests < 1:
        print("\nError: Number of requests must be positive")
        return

    normalized_path = normalize_path(args.url)

    full_url = f"http://{args.host}:{args.port}{normalized_path}"

    try:
        exec_concurrent_test(full_url, args.requests)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, stopping test...")
    except Exception as e:
        print(f"\nErrors occurred during the test: {e}")


if __name__ == "__main__":
    main()

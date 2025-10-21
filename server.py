import socket
import os
import mimetypes
import time
import urllib.parse
import argparse
import threading
from collections import defaultdict

ADDRESS = "0.0.0.0"
PORT = 1337
VALID_EXTENSIONS = ["png", "pdf", "html"]

HITS = defaultdict(int)
HITS_LOCK = threading.Lock()

CLIENT_REQUESTS = {}
CLIENT_REQUESTS_LOCK = threading.Lock()

RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_WINDOW = 1.0


def is_rate_limited(client_ip):
    current_time = time.time()

    with CLIENT_REQUESTS_LOCK:
        if client_ip not in CLIENT_REQUESTS:
            CLIENT_REQUESTS[client_ip] = []

        timestamps = CLIENT_REQUESTS[client_ip]

        cutoff_time = current_time - RATE_LIMIT_WINDOW
        timestamps[:] = [ts for ts in timestamps if ts > cutoff_time]

        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            timestamps.append(current_time)
            return True

        timestamps.append(current_time)
        return False


def get_skeleton_view():
    return r"""
    <!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.jade.min.css">
    <link rel="icon" type="image/x-icon" href="https://files.catbox.moe/6u1gw2.ico">
    <title>=(^.^)= {path}</title></head>
<body>
    <main class="container">
        <h1 style="text-align: center;">{path}</h1>
        <div style="display: flex; justify-content: center;">
        <pre style="background: none;">
      |\      _,,,---,,_
ZZZzz /,`.-'`'    -.  ;-;;,_
     |,4-  ) )-,_. ,\ (  `'-'
    '---''(_/--'  `-'\_)</pre>
        </div>
    <div>
        <table class="striped">    
        <tr>
            <th></th>
            <th>Name</th>
            <th>Last Modified</th>
            <th>Size</th>
            <th>Hits</th>
        </tr>    
        {items}
        </table>
    </div>
    </main>
</body>
</html>
    """


def get_error_view(message):
    return fr"""
    <!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.jade.min.css">
    <link rel="icon" type="image/x-icon" href="https://files.catbox.moe/6u1gw2.ico">
    <title>=(^.^)= {message}</title></head>
<body>
    <main class="container">
        <h1 style="text-align: center;">{message}</h1>
        <div style="display: flex; justify-content: center;">
        <pre style="background: none;">
      |\      _,,,---,,_
ZZZzz /,`.-'`'    -.  ;-;;,_
     |,4-  ) )-,_. ,\ (  `'-'
    '---''(_/--'  `-'\_)</pre>
        </div>
    </main>
</body>
</html>
    """


def get_rate_limit_view(client_ip):
    return fr"""
    <!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.jade.min.css">
    <link rel="icon" type="image/x-icon" href="https://files.catbox.moe/6u1gw2.ico">
    <title>=(^.^)= 429 Too Many Requests</title></head>
<body>
    <main class="container">
        <h1 style="text-align: center;">429 Too Many Requests</h1>
        <div style="display: flex; justify-content: center;">
        <pre style="background: none;">
      |\      _,,,---,,_
ZZZzz /,`.-'`'    -.  ;-;;,_
     |,4-  ) )-,_. ,\ (  `'-'
    '---''(_/--'  `-'\_)</pre>
        </div>
        <p style="text-align: center;">
            IP: {client_ip}<br>
            Rate limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} second(s)<br>
            Please slow down your requests~
        </p>
    </main>
</body>
</html>
    """


def respond(client, status, head, body):
    if isinstance(body, str):
        body_bytes = body.encode()
    else:
        body_bytes = body

    head["Content-Length"] = len(body_bytes)

    header = (f"HTTP/1.1 {status}\r\n" +
              f"\r\n".join(f"{key}: {value}" for key, value in head.items()) +
              f"\r\n\r\n")

    try:
        client.sendall(header.encode() + body_bytes)
    except (socket.error, BrokenPipeError, ConnectionResetError) as e:
        print(f"Error sending response: {e}")


def respond_400(client):
    return respond(client,
                   "400 Bad Request",
                   {"Content-Type": "text/html", "Connection": "close"},
                   get_error_view("400 Bad Request"))


def respond_404(client):
    return respond(client,
                   "404 Not Found",
                   {"Content-Type": "text/html", "Connection": "close"},
                   get_error_view("404 Not Found"))


def respond_429(client, client_ip):
    return respond(client,
                   "429 Too Many Requests",
                   {"Content-Type": "text/html", "Connection": "close"},
                   get_rate_limit_view(client_ip))


def respond_301(client, location):
    return respond(client,
                   "301 Moved Permanently",
                   {"Location": location, "Connection": "close"},
                   "")


def format_size(size):
    return (f"{size} B" if size < 1024 else
            f"{size / 1024:.1f} KB" if size < 1024 ** 2 else
            f"{size / 1024 ** 2:.1f} MB" if size < 1024 ** 3 else
            f"{size / 1024 ** 3:.1f} GB")


def format_modified_time(timestamp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def display_dir(actual_path, request_path):
    content = sorted(os.listdir(actual_path))
    filtered_content = []
    if request_path != '/':
        filtered_content.append(("⬆️", "../", "", "", ""))

    for item in content:
        item_path = os.path.join(actual_path, item)
        modified_time = format_modified_time(os.path.getmtime(item_path))

        hits = HITS.get(request_path.rstrip('/') + '/' + item, 0)

        if os.path.isdir(item_path):
            filtered_content.append(("📁", item + "/", modified_time, "-", str(hits)))
        elif item.endswith(tuple(f".{ext}" for ext in VALID_EXTENSIONS)):
            file_type = ("📄" if item.endswith('.pdf') else
                         "🖼️" if item.endswith('.png') else
                         "🌐" if item.endswith('.html') else
                         "❓")
            size = format_size(os.path.getsize(item_path))
            filtered_content.append((file_type, item, modified_time, size, str(hits)))

    view = get_skeleton_view()
    if not request_path.endswith('/'):
        request_path += '/'
    return view.format(path=request_path, items="".join(
        f"<tr><td>{file_type}</td><td><a href='{request_path}{name.rstrip('/')}'>{name}</a></td><td>{modified}</td><td>{size}</td><td>{hits}</td></tr>"
        for file_type, name, modified, size, hits in filtered_content))


def normalize_path(path):
    segments = [seg for seg in path.split('/') if seg]

    normalized_segments = []
    for segment in segments:
        if len(segment) >= 3 and segment == '.' * len(segment):
            continue
        normalized_segments.append(segment)

    return '/' + '/'.join(normalized_segments)


def increment_hits(path):
    with HITS_LOCK:
        HITS[path] += 1


def handle_client_req(client, addr, root):
    try:
        client_ip = addr[0]

        # First, receive the request
        client_request = client.recv(4096).decode(errors='ignore')

        if not client_request:
            return

        # Parse the request
        try:
            method, path, protocol = client_request.split("\r\n")[0].split(" ")
            path = urllib.parse.unquote(path)
        except (ValueError, IndexError):
            respond_400(client)
            return

        if path == "/favicon.ico":
            return

        # Check rate limit AFTER receiving the request
        if is_rate_limited(client_ip):
            print(f"Rate limit exceeded for {client_ip}")
            respond_429(client, client_ip)
            return

        print(f"Request: {method} {path} {protocol} from {addr}")
        print(f"Serving {path} to {addr}")

        original_path = path
        normalized_path = normalize_path(path)

        if original_path != normalized_path:
            respond_301(client, f"{normalized_path}")
            return

        path = normalized_path
        actual_path = os.path.realpath(os.path.join(root, path.lstrip("/")))

        if not os.path.exists(actual_path):
            respond_404(client)
            return

        if os.path.isdir(actual_path):
            content_type = "text/html"
            data = display_dir(actual_path, path)
        else:
            if not path.endswith(tuple(f".{ext}" for ext in VALID_EXTENSIONS)):
                respond_404(client)
                return

            content_type, _ = mimetypes.guess_type(actual_path)
            with open(actual_path, "rb") as requested_file:
                data = requested_file.read()

        respond(client,
                "200 OK",
                {"Content-Type": content_type, "Connection": "close"},
                data)

        increment_hits(path)

    except (ConnectionResetError, socket.error) as e:
        print(f"Error receiving request: {e}")
    finally:
        client.close()


def start_server(root):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ADDRESS, PORT))
    server.listen(100)
    print(f"Server listening on port {PORT} :3")
    print(f"Rate limiting: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s")

    try:
        while True:
            client, addr = server.accept()

            client_thread = threading.Thread(
                target=handle_client_req,
                args=(client, addr, root),
                daemon=True
            )
            client_thread.start()

    except KeyboardInterrupt:
        print("Shutting down server, nya~")
    finally:
        server.close()
        print("Server closed, bye bye~")


def main():
    parser = argparse.ArgumentParser(description="Simple HTTP File Server")
    parser.add_argument("-d", "--directory", default=".",
                        help="Root dir to serve")
    args = parser.parse_args()
    root = os.path.abspath(args.directory)
    print(root)

    start_server(root)


if __name__ == "__main__":
    main()
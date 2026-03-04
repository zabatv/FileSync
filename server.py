"""
Native HTTP server for file management
Run: python3 server.py
"""

import http.server
import socketserver
import json
import os
import shutil
from urllib.parse import urlparse, parse_qs

PORT = 5000
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'received_files')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


class FileServerHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/hello':
            self._handle_hello()

        elif parsed_path.path == '/upload':
            self._handle_upload()

        elif parsed_path.path == '/mkdir':
            self._handle_mkdir()

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_DELETE(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/delete':
            self._handle_delete()

        elif parsed_path.path == '/rmdir':
            self._handle_rmdir()

        elif parsed_path.path == '/clean':
            self._handle_clean()

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_GET(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path.startswith('/download/'):
            filename = parsed_path.path.split('/download/')[1]
            self._handle_download(filename)

        elif parsed_path.path == '/list':
            self._handle_list()

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _handle_hello(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
           ('message', 'No message')

            print(f"[HELLO] Received message: {message}")

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Server received: {message}".encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode('utf-8'))

    def _handle_upload(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))

            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write("Error: expected multipart/form-data".encode('utf-8'))
                return

            boundary = None
            if 'boundary=' in content_type:
                boundary = content_type.split('boundary=')[1].strip()
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write("Error: boundary not found".encode('utf-8'))
                return

            body = self.rfile.read(content_length)
            parts = body.split(f'--{boundary}'.encode('utf-8'))

            files_count = 0

            for part in parts:
                if not part or part == b'--' or part.startswith(b'--\r\n'):
                    continue

                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue

                header = part[:header_end].decode('utf-8', errors='ignore')
                file_data = part[header_end + 4:]

                if file_data.endswith(b'\r\n--'):
                    file_data = file_data[:-4]
                elif file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]

                filename = None
                for line in header.split('\r\n'):
                    if 'filename=' in line:
                        filename = line.split('filename=')[1].strip('"').strip("'")
                        break

                if filename and file_data:
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file_dir = os.path.dirname(file_path)
                    if file_dir and not os.path.exists(file_dir):
                        os.makedirs(file_dir, exist_ok=True)

                    with open(file_path, 'wb') as f:
                        f.write(file_data)

                    files_count += 1
                    print(f"[UPLOAD] Saved file: {filename} ({len(file_data)} bytes)")

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Uploaded files: {files_count}".encode('utf-8'))

        except Exception as e:
            print(f"[UPLOAD] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_download(self, filename):
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                file_data = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', len(file_data))
            self.end_headers()
            self.wfile.write(file_data)
            print(f"[: {filename}")
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"File not found")

    def _handle_list(self):
        try:
            files = os.listdir(UPLOAD_FOLDER)
            file_list = [f for f in files if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            response = json.dumps({'files': file_list, 'count': len(file_list)}, ensure_ascii=False)
            self.wfile.write(response.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

    def _handle_delete(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '')

            full_path = os.path.join(UPLOAD_FOLDER, path)

            if not os.path.exists(full_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Path not found: {path}".encode('utf-8'))
                return

            if os.path.isfile(full_path):
                os.remove(full_path)
                print(f"[DELETE] Removed file: {path}")
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Removed file: {path}".encode('utf-8'))
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                print(f"[DELETE] Removed directory: {path}")
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Removed directory: {path}".encode('utf-8'))
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Invalid path type: {path}".encode('utf-8'))

        except Exception as e:
            print(f"[DELETE] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_mkdir(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '')

            full_path = os.path.join(UPLOAD_FOLDER, path)

            if os.path.exists(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Path already exists: {path}".encode('utf-8'))
                return

            os.makedirs(full_path, exist_ok=True)
            print(f"[MKDIR] Created directory: {path}")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Created directory: {path}".encode('utf-8'))

        except Exception as e:
            print(f"[MKDIR] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_rmdir(self):
        try:
            content_length = int(self.headers.get('0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '')

            full_path = os.path.join(UPLOAD_FOLDER, path)

            if not os.path.exists(full_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Directory not found: {path}".encode('utf-8'))
                return

            if not os.path.isdir(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Not a directory: {path}".encode('utf-8'))
                return

            if os.listdir(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Directory not empty: {path}".encode('utf-8'))
                return

            os.rmdir(full_path)
            print(f"[RMDIR] Removed directory: {path}")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Removed directory: {path}".encode('utf-8'))

        except Exception as e:
            print(f"[RMDIR] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_clean(self):
        try:
            files = os.listdir(UPLOAD_FOLDER)
            count = 0
            for item in files:
                item_path = os.path.join(UPLOAD_FOLDER, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    count += 1

            print(f"[CLEAN] Removed {count} items")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Cleaned server: removed {count} items".encode('utf-8'))

        except Exception as e:
            print(f"[CLEAN] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[LOG] {self.address_string()} - {args[0]}")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    print("=" * 50)
    print("File server started")
    print(f"Files folder: {UPLOAD_FOLDER}")
    print(f"Port: {PORT}")
    print(f"URL: http://0.0.0.0:{PORT}")
    print("=" * 50)
    print("Press Ctrl+C to stop\n")

    with ReusableTCPServer(("", PORT), FileServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped by user")
            httpd.shutdown()

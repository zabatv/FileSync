"""
Native HTTP server for file management
Run: python3 server.py
"""

import http.server
import socketserver
import json
import os
import shutil
import zipfile
import sys
import subprocess
from urllib.parse import urlparse, parse_qs
from pathlib import Path

PORT = 5000
UPDATE_PASSWORD = "secret123"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'received_files')
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.json')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": []}

def authenticate_user(login, password):
    data = load_users()
    for user in data.get('users', []):
        if user.get('login') == login and user.get('password') == password:
            return user
    return None


class FileServerHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/hello':
            self._handle_hello()

        elif parsed_path.path == '/upload':
            self._handle_upload()

        elif parsed_path.path == '/mkdir':
            self._handle_mkdir()

        elif parsed_path.path == '/update':
            self._handle_update()

        elif parsed_path.path == '/login':
            self._handle_login()

        elif parsed_path.path == '/sync':
            self._handle_sync()

        elif parsed_path.path == '/download_sync':
            self._handle_download_sync()

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
            # Извлекаем полный путь к файлу/папке из URL
            relative_path = parsed_path.path.split('/download/', 1)[1]
            self._handle_download(relative_path)

        elif parsed_path.path == '/list':
            self._handle_list()

        elif parsed_path.path.startswith('/download_zip/'):
            # Для скачивания архива папки
            relative_path = parsed_path.path.split('/download_zip/', 1)[1]
            self._handle_download_zip(relative_path)

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _sanitize_path(self, path):
        """Очищает путь от потенциально опасных элементов"""
        # Убираем .. из пути для безопасности
        path = os.path.normpath(path).replace("..", "")
        # Обрабатываем случаи с символами, которые могут быть вредоносными
        path = path.replace("\\", "/")  # нормализуем слэши
        return path

    def _handle_hello(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            message = data.get('message', 'No message')

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
                boundary = content_type.split('boundary=')[1].strip().strip('"')
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

                if file_data and file_data.endswith(b'\r\n--'):
                    file_data = file_data[:-4]
                elif file_data and file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]

                filename = None
                filepath_header = None

                # Ищем заголовок Content-Disposition и имя файла
                for line in header.split('\r\n'):
                    if 'Content-Disposition:' in line and 'filename=' in line:
                        # Извлекаем полный путь к файлу, если он есть
                        filename_match = line.split('filename=')[1].strip('"\'')
                        # Очищаем путь от потенциально опасных элементов
                        filename = self._sanitize_path(filename_match)
                        break
                    elif 'filepath=' in line:
                        # Альтернативный способ передачи пути
                        filepath_match = line.split('filepath=')[1].strip('"\'')
                        filepath_header = self._sanitize_path(filepath_match)

                # Если передан filepath через заголовок, используем его
                final_filename = filepath_header if filepath_header else filename

                if final_filename and file_data:
                    # Создаем полный путь к файлу
                    file_path = os.path.join(UPLOAD_FOLDER, final_filename)
                    file_dir = os.path.dirname(file_path)

                    # Создаем все промежуточные директории, если они не существуют
                    if file_dir and not os.path.exists(file_dir):
                        os.makedirs(file_dir, exist_ok=True)

                    with open(file_path, 'wb') as f:
                        f.write(file_data)

                    files_count += 1
                    print(f"[UPLOAD] Saved file: {final_filename} ({len(file_data)} bytes)")

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

    def _handle_download(self, relative_path):
        """Обработка запроса на скачивание файла или папки"""
        # Очищаем путь для безопасности
        clean_path = self._sanitize_path(relative_path)
        full_path = os.path.join(UPLOAD_FOLDER, clean_path)

        if os.path.isfile(full_path):
            # Скачивание файла
            with open(full_path, 'rb') as f:
                file_data = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(clean_path)}"')
            self.send_header('Content-Length', str(len(file_data)))
            self.end_headers()
            self.wfile.write(file_data)
            print(f"[DOWNLOAD] Sent file: {clean_path}")

        elif os.path.isdir(full_path):
            # Для папки предлагаем скачать архив
            self._handle_download_zip(clean_path)
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"File or directory not found")

    def _handle_download_zip(self, relative_path):
        """Создание и отправка ZIP-архива папки"""
        clean_path = self._sanitize_path(relative_path)
        full_path = os.path.join(UPLOAD_FOLDER, clean_path)

        if not os.path.isdir(full_path):
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Directory not found")
            return

        # Создаем временный ZIP-архив
        temp_zip_path = full_path + '_temp.zip'

        try:
            # Архивируем папку
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(full_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Вычисляем относительный путь внутри архива
                        arcname = os.path.relpath(file_path, UPLOAD_FOLDER)
                        zipf.write(file_path, arcname)

            # Отправляем архив клиенту
            with open(temp_zip_path, 'rb') as f:
                zip_data = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'application/zip')
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(clean_path)}.zip"')
            self.send_header('Content-Length', str(len(zip_data)))
            self.end_headers()
            self.wfile.write(zip_data)
            print(f"[DOWNLOAD_ZIP] Sent archive for: {clean_path}")

        finally:
            # Удаляем временный архив
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)

    def _handle_list(self):
        try:
            if not os.path.exists(UPLOAD_FOLDER):
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response = json.dumps({'structure': {'files': [], 'dirs': {}}, 'count': 0}, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
                return

            def get_directory_structure(start_path):
                structure = {'files': [], 'dirs': {}}

                for item in os.listdir(start_path):
                    item_path = os.path.join(start_path, item)
                    if os.path.isfile(item_path):
                        structure['files'].append(item)
                    elif os.path.isdir(item_path):
                        structure['dirs'][item] = get_directory_structure(item_path)

                structure['files'].sort()
                return structure

            root_structure = get_directory_structure(UPLOAD_FOLDER)

            # Подсчет общего количества файлов
            def count_items(structure):
                count = len(structure['files'])
                for subdir in structure['dirs'].values():
                    count += count_items(subdir)
                return count

            total_count = count_items(root_structure)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            response = json.dumps({
                'structure': root_structure,
                'count': total_count
            }, ensure_ascii=False, indent=2)
            self.wfile.write(response.encode('utf-8'))

        except Exception as e:
            print(f"[LIST] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

    def _handle_delete(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '')

            # Очищаем путь для безопасности
            clean_path = self._sanitize_path(path)
            full_path = os.path.join(UPLOAD_FOLDER, clean_path)

            if not os.path.exists(full_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Path not found: {clean_path}".encode('utf-8'))
                return

            if os.path.isfile(full_path):
                os.remove(full_path)
                print(f"[DELETE] Removed file: {clean_path}")
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Removed file: {clean_path}".encode('utf-8'))
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                print(f"[DELETE] Removed directory: {clean_path}")
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Removed directory: {clean_path}".encode('utf-8'))
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Invalid path type: {clean_path}".encode('utf-8'))

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

            # Очищаем путь для безопасности
            clean_path = self._sanitize_path(path)
            full_path = os.path.join(UPLOAD_FOLDER, clean_path)

            if os.path.exists(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Path already exists: {clean_path}".encode('utf-8'))
                return

            # Создаем все промежуточные директории
            os.makedirs(full_path, exist_ok=True)
            print(f"[MKDIR] Created directory: {clean_path}")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Created directory: {clean_path}".encode('utf-8'))

        except Exception as e:
            print(f"[MKDIR] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_update(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            password = data.get('password', '')
            new_code = data.get('code', '')

            if password != UPDATE_PASSWORD:
                self.send_response(401)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b"Invalid password")
                return

            server_path = os.path.abspath(__file__)
            with open(server_path, 'w', encoding='utf-8') as f:
                f.write(new_code)

            print(f"[UPDATE] Code updated, will restart in 2 seconds...")

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"Code updated, restarting...")

            def restart_server():
                import time
                time.sleep(3)
                self.server.shutdown()
                subprocess.Popen([sys.executable, server_path])

            import threading
            threading.Thread(target=restart_server, daemon=False).start()
            import time
            time.sleep(0.5)

        except Exception as e:
            print(f"[UPDATE] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_login(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            login = data.get('login', '')
            password = data.get('password', '')

            user = authenticate_user(login, password)

            if user:
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response = json.dumps({
                    'success': True,
                    'login': user['login'],
                    'folders': user.get('folders', [])
                }, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
                print(f"[LOGIN] User '{login}' logged in")
            else:
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Invalid credentials'}).encode('utf-8'))

        except Exception as e:
            print(f"[LOGIN] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_sync(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            login = data.get('login', '')
            password = data.get('password', '')

            user = authenticate_user(login, password)

            if not user:
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode('utf-8'))
                return

            allowed_folders = user.get('folders', [])
            available_folders = []

            for folder in allowed_folders:
                folder_path = os.path.join(UPLOAD_FOLDER, folder)
                if os.path.isdir(folder_path):
                    files_count = sum(len(files) for _, _, files in os.walk(folder_path))
                    available_folders.append({
                        'name': folder,
                        'path': folder,
                        'files': files_count
                    })

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            response = json.dumps({
                'success': True,
                'folders': available_folders
            }, ensure_ascii=False)
            self.wfile.write(response.encode('utf-8'))

        except Exception as e:
            print(f"[SYNC] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_download_sync(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            login = data.get('login', '')
            password = data.get('password', '')
            folders = data.get('folders', [])

            user = authenticate_user(login, password)

            if not user:
                self.send_response(401)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

            allowed_folders = set(user.get('folders', []))
            requested_folders = set(folders)

            if not requested_folders.issubset(allowed_folders):
                self.send_response(403)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Access denied to some folders")
                return

            temp_zip = os.path.join(os.path.dirname(UPLOAD_FOLDER), 'sync_temp.zip')

            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for folder in requested_folders:
                    folder_path = os.path.join(UPLOAD_FOLDER, folder)
                    if os.path.isdir(folder_path):
                        for root, dirs, files in os.walk(folder_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, UPLOAD_FOLDER)
                                zipf.write(file_path, arcname)

            with open(temp_zip, 'rb') as f:
                zip_data = f.read()

            os.remove(temp_zip)

            self.send_response(200)
            self.send_header('Content-type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="sync_files.zip"')
            self.send_header('Content-Length', str(len(zip_data)))
            self.end_headers()
            self.wfile.write(zip_data)
            print(f"[SYNC] Sent sync archive to user '{login}'")

        except Exception as e:
            print(f"[SYNC] Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))

    def _handle_rmdir(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '')

            # Очищаем путь для безопасности
            clean_path = self._sanitize_path(path)
            full_path = os.path.join(UPLOAD_FOLDER, clean_path)

            if not os.path.exists(full_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Directory not found: {clean_path}".encode('utf-8'))
                return

            if not os.path.isdir(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Not a directory: {clean_path}".encode('utf-8'))
                return

            if os.listdir(full_path):
                self.send_response(400)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Directory not empty".encode('utf-8'))
                return

            os.rmdir(full_path)
            print(f"[RMDIR] Removed directory: {clean_path}")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Removed directory: {clean_path}".encode('utf-8'))

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
    print("Available endpoints:")
    print("- POST /hello: Send hello message")
    print("- POST /upload: Upload files (supports nested folders)")
    print("- GET /list: List directory structure recursively")
    print("- GET /download/<path>: Download file or directory (as ZIP)")
    print("- GET /download_zip/<path>: Download directory as ZIP")
    print("- POST /mkdir: Create directory (supports nested)")
    print("- DELETE /delete: Delete file or directory")
    print("- DELETE /rmdir: Remove empty directory")
    print("- DELETE /clean: Clean upload folder")
    print("=" * 50)
    print("Press Ctrl+C to stop\n")

    with ReusableTCPServer(("", PORT), FileServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped by user")
            httpd.shutdown()

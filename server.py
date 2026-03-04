#!/usr/bin/env python3
"""
Нативный HTTP-сервер для приёма файлов
Запуск: python3 server.py
"""

import http.server
import socketserver
import json
import os
from urllib.parse import urlparse, parse_qs

# === НАСТРОЙКИ ===
PORT = 5000
# Абсолютный путь к папке для сохранённых файлов
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'received_files')

# Создаём папку если нет
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class FileServerHandler(http.server.BaseHTTPRequestHandler):
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        
        # === Обработка /hello ===
        if parsed_path.path == '/hello':
            self._handle_hello()
        
        # === Обработка /upload ===
        elif parsed_path.path == '/upload':
            self._handle_upload()
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # === Обработка /download/<filename> ===
        if parsed_path.path.startswith('/download/'):
            filename = parsed_path.path.split('/download/')[1]
            self._handle_download(filename)
        
        # === Обработка /list (список файлов) ===
        elif parsed_path.path == '/list':
            self._handle_list()
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"404 Not Found")
    
    def _handle_hello(self):
        """Обработка приветствия"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            message = data.get('message', 'Нет сообщения')
            
            print(f"📩 [HELLO] Получено сообщение: {message}")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Сервер принял: {message}".encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Ошибка: {str(e)}".encode('utf-8'))
    
    def _handle_upload(self):
        """Обработка загрузки файлов (multipart/form-data)"""
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))
            
            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                # 🔧 ИСПРАВЛЕНО: используем .encode('utf-8') вместо b""
                self.wfile.write("Ошибка: ожидается multipart/form-data".encode('utf-8'))
                return
            
            # Извлекаем boundary
            boundary = None
            if 'boundary=' in content_type:
                boundary = content_type.split('boundary=')[1].strip()
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write("Ошибка: не найден boundary".encode('utf-8'))
                return
            
            # Читаем тело запроса
            body = self.rfile.read(content_length)
            
            # Разделяем по boundary
            parts = body.split(f'--{boundary}'.encode('utf-8'))
            
            files_count = 0
            
            for part in parts:
                # Пропускаем пустые части и границы
                if not part or part == b'--' or part.startswith(b'--\r\n'):
                    continue
                
                # Ищем заголовки части
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                
                header = part[:header_end].decode('utf-8', errors='ignore')
                file_data = part[header_end + 4:]
                
                # Удаляем завершающие \r\n
                if file_data.endswith(b'\r\n--'):
                    file_data = file_data[:-4]
                elif file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]
                
                # Извлекаем имя файла
                filename = None
                for line in header.split('\r\n'):
                    if 'filename=' in line:
                        filename = line.split('filename=')[1].strip('"').strip("'")
                        break
                
                # 🔧 ИСПРАВЛЕНО: было file_ (недописано)
                if filename and file_data:
                    # Сохраняем файл
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    
                    # Создаём подпапки если есть в имени файла
                    file_dir = os.path.dirname(file_path)
                    if file_dir and not os.path.exists(file_dir):
                        os.makedirs(file_dir, exist_ok=True)
                    
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    
                    files_count += 1
                    print(f"💾 [UPLOAD] Сохранён файл: {filename} ({len(file_data)} байт)")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Загружено файлов: {files_count}".encode('utf-8'))
            
        except Exception as e:
            print(f"❌ [UPLOAD] Ошибка: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            # 🔧 ИСПРАВЛЕНО: используем .encode('utf-8')
            self.wfile.write(f"Ошибка сервера: {str(e)}".encode('utf-8'))
    
    def _handle_download(self, filename):
        """Обработка скачивания файла"""
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
            print(f"📤 [DOWNLOAD] Отправлен файл: {filename}")
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"File not found")
    
    def _handle_list(self):
        """Возвращает список файлов на сервере"""
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
    
    def log_message(self, format, *args):
        """Переопределяем логирование"""
        print(f"🌐 [LOG] {self.address_string()} - {args[0]}")

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Файловый сервер запущен")
    print(f"📁 Папка для файлов: {UPLOAD_FOLDER}")
    print(f"🌐 Порт: {PORT}")
    print(f"🔗 URL: http://0.0.0.0:{PORT}")
    print("=" * 50)
    print("Нажмите Ctrl+C для остановки\n")
    
    with ReusableTCPServer(("", PORT), FileServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⛔ Сервер остановлен пользователем")
            httpd.shutdown()

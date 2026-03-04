#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
from urllib.parse import urlparse, parse_qs

PORT = 5000
UPLOAD_FOLDER = 'received_files'

# Создаём папку для файлов
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class MyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
    parsed_path = urlparse(self.path)
    
    if parsed_path.path == '/hello':
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        message = data.get('message', 'Нет сообщения')
        
        print(f"📩 Получено сообщение: {message}")
        
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(f"Сервер принял: {message}".encode('utf-8'))
    
    elif parsed_path.path == '/upload':
        content_type = self.headers.get('Content-Type', '')
        content_length = int(self.headers['Content-Length'])
        
        # Обработка multipart/form-data
        if 'multipart/form-data' in content_type:
            boundary = content_type.split('boundary=')[1] if 'boundary=' in content_type else None
            
            if boundary:
                body = self.rfile.read(content_length)
                
                # Парсим multipart данные
                parts = body.split(f'--{boundary}'.encode('utf-8'))
                
                for part in parts:
                    if b'filename=' in part:
                        # Извлекаем имя файла
                        header_end = part.find(b'\r\n\r\n')
                        if header_end == -1:
                            continue
                        
                        header = part[:header_end].decode('utf-8', errors='ignore')
                        
                        # Ищем filename в заголовке
                        for line in header.split('\r\n'):
                            if 'filename=' in line:
                                filename = line.split('filename=')[1].strip('"').strip("'")
                                break
                        else:
                            continue
                        
                        # Данные файла (после заголовков)
                        file_data = part[header_end + 4:]
                        
                        # Удаляем лишние \r\n в конце
                        if file_data.endswith(b'\r\n'):
                            file_data = file_data[:-2]
                        elif file_data.endswith(b'\n'):
                            file_data = file_data[:-1]
                        
                        # Сохраняем файл
                        if filename and file_data:
                            file_path = os.path.join(UPLOAD_FOLDER, filename)
                            
                            # Создаём подпапки если нужно
                            os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else UPLOAD_FOLDER, exist_ok=True)
                            
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            
                            print(f"💾 Файл сохранён: {filename} ({len(file_data)} байт)")
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Загружено файлов: {len([p for p in parts if b'filename=' in p])}".encode('utf-8'))
                return
        
        # Простая загрузка одного файла (для совместимости)
        else:
            filename = self.headers.get('X-Filename', 'uploaded_file')
            file_data = self.rfile.read(content_length)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            print(f"💾 Файл сохранён: {filename}")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Файл {filename} сохранён!".encode('utf-8'))
    
    else:
        self.send_response(404)
        self.end_headers()

    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # Обработка /download/<filename>
        if parsed_path.path.startswith('/download/'):
            filename = parsed_path.path.split('/download/')[1]
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', len(file_data))
                self.end_headers()
                self.wfile.write(file_data)
                print(f"📤 Файл отправлен: {filename}")
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Переопределяем, чтобы видеть логи в реальном времени
        print(f"🌐 {args[0]}")

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"🚀 Сервер запущен на порту {PORT}")
        print(f"📁 Папка для файлов: {os.path.abspath(UPLOAD_FOLDER)}")
        httpd.serve_forever()

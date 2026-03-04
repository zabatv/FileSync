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
        
        # Обработка /hello
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
        
        # Обработка /upload
        elif parsed_path.path == '/upload':
            content_length = int(self.headers['Content-Length'])
            content_type = self.headers.get('Content-Type', '')
            
            # Получаем имя файла из заголовка Content-Disposition
            filename = None
            if 'filename=' in content_type:
                filename = content_type.split('filename=')[1].split(';')[0].strip('"')
            elif 'Content-Disposition' in self.headers:
                disp = self.headers['Content-Disposition']
                if 'filename=' in disp:
                    filename = disp.split('filename=')[1].strip('"')
            
            if not filename:
                filename = 'uploaded_file.zip'
            
            # Читаем и сохраняем файл
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

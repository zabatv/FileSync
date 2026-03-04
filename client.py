#!/usr/bin/env python3
"""
Универсальный клиент для работы с файловым сервером
Использование:
    python client.py --s <путь_к_папке>   - отправить файлы
    python client.py --d <имя_файла>      - скачать файл
    python client.py --list               - список файлов на сервере
"""

import http.client
import os
import sys
import mimetypes
import uuid
import time
import json
import argparse

# === НАСТРОЙКИ ===
# ⚠️ ЗАМЕНИТЕ НА IP ВАШЕГО СЕРВЕРА
SERVER_IP = '127.0.0.1'
SERVER_PORT = 5000
DOWNLOAD_FOLDER = './downloaded_files'


# =============================================================================
# ФУНКЦИИ ОТПРАВКИ (--s)
# =============================================================================

def create_multipart_form_data(files):
    """Создаёт тело запроса в формате multipart/form-data"""
    boundary = uuid.uuid4().hex
    body = b''
    
    for file_path in files:
        filename = os.path.basename(file_path)
        body += f'--{boundary}\r\n'.encode('utf-8')
        body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode('utf-8')
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        body += f'Content-Type: {content_type}\r\n'.encode('utf-8')
        body += b'\r\n'
        with open(file_path, 'rb') as f:
            body += f.read()
        body += b'\r\n'
    
    body += f'--{boundary}--\r\n'.encode('utf-8')
    return body, boundary


def send_files(folder_path):
    """Отправляет все файлы из папки на сервер"""
    if not os.path.isdir(folder_path):
        print(f"❌ Папка не найдена: {folder_path}")
        return False
    
    files = []
    for root, dirs, filenames in os.walk(folder_path):
        for filename in filenames:
            if filename.startswith('.'):
                continue
            file_path = os.path.join(root, filename)
            files.append(file_path)
    
    if not files:
        print(f"⚠️  В папке нет файлов: {folder_path}")
        return False
    
    total_size = sum(os.path.getsize(f) for f in files)
    print(f"📁 Найдено файлов: {len(files)}")
    print(f"📊 Общий размер: {total_size / 1024:.2f} KB")
    
    start_time = time.time()
    body, boundary = create_multipart_form_data(files)
    
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    try:
        print(f"🚀 Отправка на сервер {SERVER_IP}:{SERVER_PORT}...")
        conn.request('POST', '/upload', body, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        elapsed = time.time() - start_time
        
        if response.status == 200:
            print(f"✅ Успешно за {elapsed:.2f} сек!")
            print(f"📝 Ответ сервера: {data}")
            return True
        else:
            print(f"❌ Ошибка сервера ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()


# =============================================================================
# ФУНКЦИИ СКАЧИВАНИЯ (--d)
# =============================================================================

def download_file(filename):
    """Скачивает файл с сервера"""
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
    
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)
    
    try:
        print(f"📥 Скачивание: {filename}")
        conn.request('GET', f'/download/{filename}')
        response = conn.getresponse()
        
        if response.status == 200:
            file_data = response.read()
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)
            print(f"✅ Файл сохранён: {file_path} ({len(file_data)} байт)")
            return True
        elif response.status == 404:
            print(f"❌ Файл не найден на сервере")
            return False
        else:
            print(f"❌ Ошибка сервера: {response.status}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()


def list_files():
    """Получает список файлов на сервере"""
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)
    
    try:
        conn.request('GET', '/list')
        response = conn.getresponse()
        
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            print(f"📁 Файлы на сервере ({data['count']}):")
            for f in data['files']:
                print(f"   - {f}")
            return True
        else:
            print(f"❌ Ошибка: {response.status}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Клиент для работы с файловым сервером',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python client.py --s ./my_folder       Отправить папку на сервер
  python client.py --d file.txt          Скачать файл с сервера
  python client.py --list                Показать список файлов на сервере
  python client.py --hello               Проверить связь с сервером
        """
    )
    
    parser.add_argument('--s', '--send', metavar='FOLDER', help='Отправить папку на сервер')
    parser.add_argument('--d', '--download', metavar='FILE', help='Скачать файл с сервера')
    parser.add_argument('--list', action='store_true', help='Список файлов на сервере')
    parser.add_argument('--hello', action='store_true', help='Проверить связь с сервером')
    
    args = parser.parse_args()
    
    # Если нет аргументов - показать справку
    if not (args.s or args.d or args.list or args.hello):
        parser.print_help()
        sys.exit(1)
    
    # Проверка связи
    if args.hello:
        conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=10)
        try:
            conn.request('POST', '/hello', json.dumps({'message': 'Hello from client'}).encode('utf-8'), {'Content-Type': 'application/json'})
            response = conn.getresponse()
            print(f"📡 Статус сервера: {response.status}")
            print(f"📝 Ответ: {response.read().decode('utf-8')}")
            conn.close()
        except Exception as e:
            print(f"❌ Сервер недоступен: {e}")
            sys.exit(1)
    
    # Отправка файлов
    if args.s:
        folder = args.s
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        print(f"📂 Отправляем папку: {folder}")
        print("-" * 50)
        success = send_files(folder)
        sys.exit(0 if success else 1)
    
    # Скачивание файла
    if args.d:
        print("-" * 50)
        success = download_file(args.d)
        sys.exit(0 if success else 1)
    
    # Список файлов
    if args.list:
        print("-" * 50)
        success = list_files()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

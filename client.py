import http.client
import os
import sys
import json

# === НАСТРОЙКИ ===
# ⚠️ ЗАМЕНИТЕ НА IP ВАШЕГО СЕРВЕРА
SERVER_IP = '192.168.0.'
SERVER_PORT = 5000
DOWNLOAD_FOLDER = './downloaded_files'


def download_file(filename):
    """Скачивает файл с сервера"""

    # Создаём папку для загрузок
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


def main():
    if len(sys.argv) < 2:
        print("=" * 50)
        print("📥 Скачивание файлов с сервера")
        print("=" * 50)
        print("Использование:")
        print("  python download_file.py <имя_файла>  - скачать файл")
        print("  python download_file.py --list       - список файлов")
        print("=" * 50)
        sys.exit(1)

    if sys.argv[1] == '--list':
        list_files()
    else:
        download_file(sys.argv[1])


if __name__ == '__main__':
    main()

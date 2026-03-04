"""
File server client for uploading, downloading, and managing files/folders
Usage:
    python client.py --s <path_to_folder>   - upload files
    python client.py --d <filename>         - download file
    python client.py --list                 - list files on server
    python client.py --delete <path>        - delete file/folder
    python client.py --mkdir <path>         - create directory
    python client.py --rmdir <path>         - remove directory
    python client.py --clean                - delete all files
"""

import http.client
import os
import sys
import mimetypes
import uuid
import time
import json
import argparse
import shutil

# CONFIGURATION
SERVER_IP = '192.168.0.104'
SERVER_PORT = 5000
DOWNLOAD_FOLDER = './downloaded_files'


def create_multipart_form_data(files):
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
    if not os.path.isdir(folder_path):
        print(f"Directory not found: {folder_path}")
        return False

    files = []
    for root, dirs, filenames in os.walk(folder_path):
        for filename in filenames:
            if filename.startswith('.'):
                continue
            file_path = os.path.join(root, filename)
            files.append(file_path)

    if not files:
        print(f"No files found in directory: {folder_path}")
        return False

    total_size = sum(os.path.getsize(f) for f in files)
    print(f"Files found: {len(files)}")
    print(f"Total size: {total_size / 1024:.2f} KB")

    start_time = time.time()
    body, boundary = create_multipart_form_data(files)

    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }

    try:
        print(f"Uploading to server {SERVER_IP}:{SERVER_PORT}...")
        conn.request('POST', '/upload', body, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        elapsed = time.time() - start_time

        if response.status == 200:
            print(f"Success in {elapsed:.2f} seconds!")
            print(f"Server response: {data}")
            return True
        else:
            print(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def download_file(filename):
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        print(f"Downloading: {filename}")
        conn.request('GET', f'/download/{filename}')
        response = conn.getresponse()

        if response.status == 200:
            file_data = response.read()
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)
            print(f"File saved: {file_path} ({len(file_data)} bytes)")
            return True
        elif response.status == 404:
            print(f"File not found on server")
            return False
        else:
            print(f"Server error: {response.status}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def list_files():
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        conn.request('GET', '/list')
        response = conn.getresponse()

        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            print(f"Files on server ({data['count']}):")
            for f in data['files']:
                print(f"   - {f}")
            return True
        else:
            print(f"Error: {response.status}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def delete_path(path):
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        print(f"Deleting: {path}")
        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        
        conn.request('DELETE', '/delete', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            print(f"Successfully deleted: {path}")
            print(f"Server response: {data}")
            return True
        elif response.status == 404:
            print(f"Path not found on server: {path}")
            return False
        else:
            print(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def create_directory(path):
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        print(f"Creating directory: {path}")
        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        
        conn.request('POST', '/mkdir', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            print(f"Successfully created directory: {path}")
            print(f"Server response: {data}")
            return True
        else:
            print(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def remove_directory(path):
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        print(f"Removing directory: {path}")
        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        
        conn.request('DELETE', '/rmdir', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            print(f"Successfully removed directory: {path}")
            print(f"Server response: {data}")
            return True
        elif response.status == 404:
            print(f"Directory not found on server: {path}")
            return False
        elif response.status == 400:
            print(f"Directory not empty: {path}")
            print(f"Server response: {data}")
            return False
        else:
            print(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def clean_server():
    conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=30)

    try:
        print("Cleaning server (deleting all files)...")
        conn.request('DELETE', '/clean')
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            print("Successfully cleaned server")
            print(f"Server response: {data}")
            return True
        else:
            print(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Client for managing file server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python client.py --s ./my_folder       Upload folder to server
  python client.py --d file.txt          Download file from server
  python client.py --list                Show list of files on server
  python client.py --delete file.txt     Delete file from server
  python client.py --mkdir new_folder    Create directory on server
  python client.py --rmdir folder_name   Remove directory from server
  python client.py --clean on server
  python client.py --hello               Check server connection
        """
    )

    parser.add_argument('--s', '--send', metavar='FOLDER', help='Upload folder to server')
    parser.add_argument('--d', '--download', metavar='FILE', help='Download file from server')
    parser.add_argument('--list', action='store_true', help='List files on server')
    parser.add_argument('--delete', metavar='PATH', help='Delete file/folder from server')
    parser.add_argument('--mkdir', metavar='PATH', help='Create directory on server')
    parser.add_argument('--rmdir', metavar='PATH', help='Remove directory from server')
    parser.add_argument('--clean', action='store_true', help='Delete all files from server')
    parser.add_argument('--hello', action='store_true', help='Check server connection')

    args = parser.parse_args()

    if not (args.s or args.d or args.list or args.delete or args.mkdir or args.rmdir or args.clean or args.hello):
        parser.print_help()
        sys.exit(1)

    if args.hello:
        conn = http.client.HTTPConnection(SERVER_IP, SERVER_PORT, timeout=10)
        try:
            conn.request('POST', '/hello', json.dumps({'message': 'Hello from client'}).encode('utf-8'),
                         {'Content-Type': 'application/json'})
            response = conn.getresponse()
            print(f"Server status: {response.status}")
            print(f"Response: {response.read().decode('utf-8')}")
            conn.close()
        except Exception as e:
            print(f"Server unavailable: {e}")
            sys.exit(1)

    if args.s:
        folder = args.s
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        print(f"Sending folder: {folder}")
        print("-" * 50)
        success = send_files(folder)
        sys.exit(0 if success else 1)

    if args.d:
        print("-" * 50)
        success = download_file(args.d)
        sys.exit(0 if success else 1)

    if args.list:
        print("-" * 50)
        success = list_files()
        sys.exit(0 if success else 1)

    if args.delete:
        print("-" * 50)
        success = delete_path(args.delete)
        sys.exit(0 if success else 1)

    if args.mkdir:
        print("-" * 50)
        success = create_directory(args.mkdir)
        sys.exit(0 if success else 1)

    if args.rmdir:
        print("-" * 50)
        success = remove_directory(args.rmdir)
        sys.exit(0 if success else 1)

    if args.clean:
        print("-" * 50)
        success = clean_server()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

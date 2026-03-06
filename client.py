"""
File server client for uploading, downloading, and managing files/folders
Usage:
    python client.py --ip <xxx.xxx.xxx.xxx> --s <path_to_folder>   - upload files
    python client.py --ip <xxx.xxx.xxx.xxx> --d <filename>         - download file
    python client.py --ip <xxx.xxx.xxx.xxx> --list                 - list files on server
    python client.py --ip <xxx.xxx.xxx.xxx> --delete <path>        - delete file/folder
    python client.py --ip <xxx.xxx.xxx.xxx> --mkdir <path>         - create directory
    python client.py --ip <xxx.xxx.xxx.xxx> --rmdir <path>         - remove directory
    python client.py --ip <xxx.xxx.xxx.xxx> --clean                - delete all files
"""

import http.client
import os
import sys
import mimetypes
import uuid
import time
import json
import argparse
import threading
import itertools
from urllib.parse import quote

# DEFAULT CONFIGURATION
DEFAULT_SERVER_IP = '192.168.0.104'
SERVER_PORT = 5000
DOWNLOAD_FOLDER = './downloaded_files'

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")

def print_error(msg):
    print(f"{Colors.RED}✗{Colors.END} {msg}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.END} {msg}")

def print_header(msg):
    print(f"{Colors.CYAN}{Colors.BOLD}{msg}{Colors.END}")

def print_progress_bar(current, total, prefix='', bar_length=30):
    if total == 0:
        return
    percent = current / total
    filled = int(bar_length * percent)
    bar = '█' * filled + '░' * (bar_length - filled)
    percent_str = f"{percent * 100:.1f}%"
    sys.stdout.write(f'\r{prefix} [{bar}] {percent_str}')
    sys.stdout.flush()
    if current >= total:
        print()

class Spinner:
    def __init__(self, message="Loading"):
        self.message = message
        self.running = False
        self.thread = None

    def spin(self):
        for char in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']):
            if not self.running:
                break
            sys.stdout.write(f'\r{self.message} {char}')
            sys.stdout.flush()
            time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin, daemon=True)
        self.thread.start()

    def stop(self, message="Done"):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        sys.stdout.write('\r' + ' ' * (len(self.message) + 3) + '\r')
        print_success(message)


def create_multipart_form_data(files, base_path):
    boundary = uuid.uuid4().hex
    body = b''

    for file_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        filename = os.path.basename(file_path)

        # Include subdirectory information in filename if needed
        parent_dir = os.path.dirname(rel_path).replace('\\', '/')
        if parent_dir != '.' and parent_dir != '':
            # Send the full relative path so server can recreate folder structure
            full_filename = f"{parent_dir}/{filename}"
        else:
            full_filename = filename

        body += f'--{boundary}\r\n'.encode('utf-8')
        body += f'Content-Disposition: form-data; name="file"; filename="{full_filename}"\r\n'.encode('utf-8')
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        body += f'Content-Type: {content_type}\r\n'.encode('utf-8')
        body += b'\r\n'
        with open(file_path, 'rb') as f:
            body += f.read()
        body += b'\r\n'

    body += f'--{boundary}--\r\n'.encode('utf-8')
    return body, boundary


def ensure_remote_dirs(remote_path, server_ip, server_port):
    """Ensure all directories in the remote path exist on the server"""
    path_parts = remote_path.replace('\\', '/').split('/')

    # Build path incrementally and create missing directories
    current_path = ""
    for part in path_parts[:-1]:  # Exclude the final filename
        if part == "":  # Skip leading empty string from absolute paths
            continue
        if current_path == "":
            current_path = part
        else:
            current_path = f"{current_path}/{part}"

        # Check if directory exists and create if needed
        conn = http.client.HTTPConnection(server_ip, server_port, timeout=10)
        try:
            payload = json.dumps({"path": current_path}).encode('utf-8')
            headers = {'Content-Type': 'application/json'}

            conn.request('POST', '/mkdir', payload, headers)
            response = conn.getresponse()
            response.read()  # Consume response
            # We don't care about errors here since directory might already exist
        except Exception as e:
            pass
        finally:
            conn.close()


def send_files(folder_path, server_ip, server_port):
    if not os.path.isdir(folder_path):
        print(f"Directory not found: {folder_path}")
        return False

    files = []
    base_path = os.path.normpath(folder_path)

    for root, dirs, filenames in os.walk(folder_path):
        for filename in filenames:
            if filename.startswith('.'):
                continue
            file_path = os.path.join(root, filename)
            files.append(file_path)

    if not files:
        print_error(f"No files found in directory: {folder_path}")
        return False

    total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
    print_info(f"Files found: {len(files)}")
    print_info(f"Total size: {total_size / 1024:.2f} KB")

    spinner = Spinner("Preparing upload")
    spinner.start()

    for file_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        if os.path.sep in rel_path:
            remote_dir = os.path.dirname(rel_path).replace('\\', '/')
            ensure_remote_dirs(remote_dir, server_ip, server_port)

    body, boundary = create_multipart_form_data(files, base_path)
    spinner.stop("Prepared")

    start_time = time.time()
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=60)
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }

    print_header(f"↑ Uploading to {server_ip}:{server_port}")
    print_progress_bar(0, 100, "Upload")

    try:
        conn.request('POST', '/upload', body, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        elapsed = time.time() - start_time

        print_progress_bar(100, 100, "Upload")

        if response.status == 200:
            speed = total_size / 1024 / elapsed if elapsed > 0 else 0
            print_success(f"Uploaded {len(files)} files in {elapsed:.2f}s ({speed:.1f} KB/s)")
            print_info(f"Server: {data}")
            return True
        else:
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def download_file(filename, server_ip, server_port):
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    conn = http.client.HTTPConnection(server_ip, server_port, timeout=60)

    try:
        print_header(f"↓ Downloading: {filename}")
        encoded_filename = quote(filename, safe='/')
        
        spinner = Spinner("Connecting")
        spinner.start()
        
        conn.request('GET', f'/download/{encoded_filename}')
        response = conn.getresponse()
        spinner.stop("Connected")

        if response.status == 200:
            file_data = response.read()
            content_length = int(response.getheader('Content-Length', len(file_data)))

            print_progress_bar(0, content_length, "Download")

            local_file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            local_dir = os.path.dirname(local_file_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)

            with open(local_file_path, 'wb') as f:
                f.write(file_data)

            print_progress_bar(content_length, content_length, "Download")
            size_kb = len(file_data) / 1024
            print_success(f"Saved: {local_file_path} ({size_kb:.2f} KB)")
            return True
        elif response.status == 404:
            print_error("File not found on server")
            return False
        else:
            print_error(f"Server error: {response.status}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def list_files(server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)

    try:
        print_info("Fetching file list...")
        spinner = Spinner("Loading")
        spinner.start()
        
        conn.request('GET', '/list')
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        
        spinner.stop("Done")

        if response.status == 200:
            data = json.loads(data)
            
            def flatten_files(structure):
                result = []
                for f in structure.get('files', []):
                    result.append(f)
                for subdir, substructure in structure.get('dirs', {}).items():
                    for f in flatten_files(substructure):
                        result.append(f"{subdir}/{f}")
                return result
            
            all_files = flatten_files(data['structure'])
            count = data['count']
            
            print_header(f"📁 Files on server ({count}):")
            print("-" * 40)
            if count == 0:
                print_info("No files found")
            else:
                for f in sorted(all_files):
                    print(f"  📄 {f}")
            print("-" * 40)
            return True
        else:
            print_error(f"Error: {response.status}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def delete_path(path, server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)

    try:
        print_header(f"🗑️  Deleting: {path}")
        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        spinner = Spinner("Deleting")
        spinner.start()
        
        conn.request('DELETE', '/delete', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            spinner.stop("Deleted")
            print_success(f"Deleted: {path}")
            return True
        elif response.status == 404:
            spinner.stop("Not found")
            print_error(f"Path not found: {path}")
            return False
        else:
            spinner.stop("Error")
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def create_directory(path, server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)

    try:
        print_header(f"📁 Creating directory: {path}")
        
        spinner = Spinner("Creating")
        spinner.start()
        
        ensure_remote_dirs(path, server_ip, server_port)

        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        conn.request('POST', '/mkdir', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            spinner.stop("Created")
            print_success(f"Created: {path}")
            return True
        else:
            spinner.stop("Error")
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def remove_directory(path, server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)

    try:
        print_header(f"📁 Removing directory: {path}")
        
        spinner = Spinner("Removing")
        spinner.start()
        
        payload = json.dumps({"path": path}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        conn.request('DELETE', '/rmdir', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            spinner.stop("Removed")
            print_success(f"Removed directory: {path}")
            return True
        elif response.status == 404:
            spinner.stop("Not found")
            print_error(f"Directory not found: {path}")
            return False
        elif response.status == 400:
            spinner.stop("Not empty")
            print_error(f"Directory not empty: {path}")
            return False
        else:
            spinner.stop("Error")
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def clean_server(server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)

    try:
        print_header("🧹 Cleaning server (deleting all files)...")
        
        spinner = Spinner("Cleaning")
        spinner.start()
        
        conn.request('DELETE', '/clean')
        response = conn.getresponse()
        data = response.read().decode('utf-8')

        if response.status == 200:
            spinner.stop("Cleaned")
            print_success("Server cleaned successfully")
            return True
        else:
            spinner.stop("Error")
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False
    finally:
        conn.close()


def check_server_connection(server_ip, server_port):
    conn = http.client.HTTPConnection(server_ip, server_port, timeout=10)
    try:
        print_info(f"Connecting to {server_ip}:{server_port}...")
        
        spinner = Spinner("Connecting")
        spinner.start()
        
        conn.request('POST', '/hello', json.dumps({'message': 'Hello from client'}).encode('utf-8'),
                     {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        
        spinner.stop("Connected")
        
        print_success(f"Server is online! (Status: {response.status})")
        print_info(f"Response: {data}")
        conn.close()
        return True
    except Exception as e:
        print_error(f"Server unavailable: {e}")
        return False


def update_server(code_file, server_ip, server_port, password):
    try:
        with open(code_file, 'r', encoding='utf-8') as f:
            code = f.read()

        print_header(f"🔄 Updating server with {code_file}")
        
        spinner = Spinner("Updating")
        spinner.start()

        payload = json.dumps({'password': password, 'code': code}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        conn = http.client.HTTPConnection(server_ip, server_port, timeout=30)
        conn.request('POST', '/update', payload, headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        conn.close()

        if response.status == 200:
            spinner.stop("Updated")
            print_success("Server code updated! Restarting...")
            print_info("Wait a few seconds before reconnecting")
            return True
        else:
            spinner.stop("Error")
            print_error(f"Server error ({response.status}): {data}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Client for managing file server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python client.py --ip 192.168.1.100 --s ./my_folder          Upload folder to server (with subdirectories)
  python client.py --ip 192.168.1.100 --d file.txt            Download file from server
  python client.py --ip 192.168.1.100 --list                  Show list of files on server
  python client.py --ip 192.168.1.100 --delete file.txt       Delete file from server
  python client.py --ip 192.168.1.100 --mkdir new/folder      Create nested directory on server
  python client.py --ip 192.168.1.100 --rmdir new/folder   Remove directory from server
  python client.py --ip 192.168.1.100 --clean                 Clean all files on server
  python client.py --ip 192.168.1.100 --hello                 Check server connection
  python client.py --ip 192.168.1.100 --update server.py --password secret123   Update server code
        """
    )

    parser.add_argument('--ip', metavar='IP', default=DEFAULT_SERVER_IP,
                        help=f'Specify the server IP address (default: {DEFAULT_SERVER_IP})')
    parser.add_argument('--port', metavar='PORT', type=int, default=SERVER_PORT,
                        help=f'Specify the server port (default: {SERVER_PORT})')
    parser.add_argument('--s', '--send', metavar='FOLDER', help='Upload folder to server (preserves subdirectory structure)')
    parser.add_argument('--d', '--download', metavar='FILE', help='Download file from server (supports paths like dir/file.txt)')
    parser.add_argument('--list', action='store_true', help='List files on server')
    parser.add_argument('--delete', metavar='PATH', help='Delete file/folder from server (supports paths like dir/file.txt)')
    parser.add_argument('--mkdir', metavar='PATH', help='Create directory on server (creates parent dirs if needed)')
    parser.add_argument('--rmdir', metavar='PATH', help='Remove directory from server')
    parser.add_argument('--clean', action='store_true', help='Delete all files from server')
    parser.add_argument('--hello', action='store_true', help='Check server connection')
    parser.add_argument('--update', metavar='FILE', help='Update server with new code')
    parser.add_argument('--password', metavar='PASS', help='Password for server update')

    args = parser.parse_args()

    if not (args.s or args.d or args.list or args.delete or args.mkdir or args.rmdir or args.clean or args.hello or args.update):
        parser.print_help()
        sys.exit(1)

    server_ip = args.ip
    server_port = args.port

    print(f"{Colors.CYAN}╔════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.CYAN}║     File Server Client v2.0           ║{Colors.END}")
    print(f"{Colors.CYAN}╚════════════════════════════════════════╝{Colors.END}")
    print(f"{Colors.YELLOW}Server: {server_ip}:{server_port}{Colors.END}")
    print("-" * 40)

    if args.hello:
        success = check_server_connection(server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.s:
        folder = args.s
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        print(f"📂 Sending: {folder}")
        print("-" * 40)
        success = send_files(folder, server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.d:
        success = download_file(args.d, server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.list:
        success = list_files(server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.delete:
        success = delete_path(args.delete, server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.mkdir:
        success = create_directory(args.mkdir, server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.rmdir:
        success = remove_directory(args.rmdir, server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.clean:
        success = clean_server(server_ip, server_port)
        sys.exit(0 if success else 1)

    if args.update:
        if not args.password:
            print_error("--password is required for update")
            sys.exit(1)
        if not os.path.exists(args.update):
            print_error(f"File not found: {args.update}")
            sys.exit(1)
        print(f"📝 Updating with: {args.update}")
        print("-" * 40)
        success = update_server(args.update, server_ip, server_port, args.password)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

from flask import Flask, request, send_from_directory, abort
import os

app = Flask(__name__)

UPLOAD_FOLDER = '/home/USER_NAME/file_server/received_files'  # ЗАМЕНИТЕ USER_NAME на ваше имя пользователя
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/hello', methods=['POST'])
def hello():
    data = request.get_json()
    if data and 'message' in data:
        msg = data['message']
        print(f"📩 Получено сообщение: {msg}")
        return f"Сервер принял: {msg}", 200
    return "Нет сообщения", 400

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'Нет файла', 400
    file = request.files['file']
    if file.filename == '':
        return 'Файл не выбран', 400
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    return f'Файл {file.filename} успешно сохранен!', 200

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

if __name__ == '__main__':
    print("🚀 Сервер запущен...")
    app.run(host='0.0.0.0', port=5000)

import os
import shutil
import random
import threading
import time
import mimetypes
import urllib.parse
import json
from flask import Flask, render_template, request, redirect, url_for, send_file,after_this_request

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

# 用于存储文件信息和下载次数
file_info = {}


def generate_download_code():
    return ''.join(random.choices('0123456789', k=6))


def save_file_info():
    with open('file_info.json', 'w') as f:
        json.dump(file_info, f)


def load_file_info():
    global file_info
    if os.path.exists('file_info.json'):
        with open('file_info.json', 'r') as f:
            file_info = json.load(f)

# ** 服务器启动时自动加载 JSON 文件 **
load_file_info()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return '未找到文件', 400

    file = request.files['file']
    if file.filename == '':
        return '文件名为空', 400

    download_code = ''.join(random.choices('0123456789', k=6))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], download_code)
    os.makedirs(file_path, exist_ok=True)

    file.save(os.path.join(file_path, file.filename))

    # ** 存储文件信息并保存到 JSON **
    download_count = int(request.form.get('download_count', 2))
    file_info[download_code] = {
        'path': file_path,
        'count': download_count,
        'filename': file.filename
    }
    save_file_info()  # ⚡ 保存数据

    return f'上传成功！下载码：{download_code}'


def delayed_delete(path, delay=5):
    time.sleep(delay)
    shutil.rmtree(path, ignore_errors=True)

@app.route('/download', methods=['POST', 'GET'])
def download():
    # ** 从 URL 参数或表单获取下载码 **
    download_code = request.args.get('download_code', '').strip() if request.method == 'GET' else request.form.get('download_code', '').strip()

    # ** 检查下载码是否有效 **
    if not download_code or download_code not in file_info:
        return '无效的下载码', 400

    info = file_info[download_code]
    info['count'] -= 1
    file_path = os.path.join(info['path'], info['filename'])

    # ** 确保文件存在 **
    if not os.path.exists(file_path):
        return '文件不存在', 404

    # ** 确保 MIME 类型正确 **
    mimetype, _ = mimetypes.guess_type(file_path)
    if mimetype is None:
        mimetype = 'application/octet-stream'

    try:
        response = send_file(file_path, as_attachment=True, mimetype=mimetype)

        # ** 处理中文文件名 **
        encoded_filename = urllib.parse.quote(info['filename'])
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"

        # ** 如果下载次数用尽，删除文件 **
        if info['count'] <= 0:
            del file_info[download_code]
            save_file_info()  # ⚡ 立即保存数据
            threading.Thread(target=delayed_delete, args=(info['path'], 5)).start()

        return response

    except Exception as e:
        return f"服务器错误: {str(e)}", 500


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000)
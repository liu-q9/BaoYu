# -*- coding: utf-8 -*-
"""鲍鱼数据分析系统 - 后端API服务器"""

import json
import math
import random
import sqlite3
import os
import http.server
import urllib.parse
import time
import re
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), 'abalone.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS abalone (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sex INTEGER, length REAL, diameter REAL, height REAL,
        whole_weight REAL, shucked_weight REAL,
        viscera_weight REAL, shell_weight REAL, rings INTEGER
    )''')
    # Insert sample data if empty
    c.execute('SELECT COUNT(*) FROM abalone')
    if c.fetchone()[0] == 0:
        sexes = [-1, 0, 1]
        sex_names = ['幼年', '雄性', '雌性']
        for i in range(1, 87):
            sex = sexes[i % 3]
            length = round(0.3 + random.random() * 0.5, 3)
            diameter = round(0.2 + random.random() * 0.3, 3)
            height = round(0.05 + random.random() * 0.15, 3)
            whole_weight = round(0.2 + random.random() * 1.0, 4)
            shucked_weight = round(0.1 + random.random() * 0.5, 4)
            viscera_weight = round(0.05 + random.random() * 0.2, 4)
            shell_weight = round(0.05 + random.random() * 0.3, 4)
            rings = random.randint(3, 29)
            c.execute('''INSERT INTO abalone (sex,length,diameter,height,whole_weight,shucked_weight,viscera_weight,shell_weight,rings)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (sex, length, diameter, height, whole_weight, shucked_weight, viscera_weight, shell_weight, rings))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Simple linear regression model for prediction
def predict_rings(features):
    sex, length, diameter, height, whole_weight, shucked_weight, viscera_weight, shell_weight = features
    rings = round(5 + length * 8 + diameter * 6 + height * 10 + whole_weight * 2
                  - shucked_weight * 1.5 + viscera_weight * 3 + shell_weight * 4
                  + (2 if sex == 1 else 1 if sex == 0 else 0) + (random.random() - 0.5) * 3)
    return max(1, min(29, rings))

class APIHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        mime_map = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.ico': 'image/x-icon',
            '.webp': 'image/webp',
        }
        content_type = mime_map.get(ext, 'application/octet-stream')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_json({'error': 'Not Found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API routes
        if path == '/api/abalone':
            self._handle_get_abalone(query)
        elif path.startswith('/api/abalone/'):
            id_str = path.split('/')[-1]
            self._handle_get_abalone_by_id(id_str)
        elif path == '/api/stats':
            self._handle_get_stats()
        elif path == '/api/train/history':
            self._handle_get_train_history()
        elif path == '/api/check':
            self._send_json({'status': 'ok', 'message': '服务器运行正常'})
        else:
            # Serve static files
            base_dir = os.path.dirname(__file__)
            if path == '/' or path == '':
                path = '/index.html'
            filepath = os.path.join(base_dir, path.lstrip('/'))
            self._send_file(filepath)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        data = json.loads(body.decode('utf-8')) if body else {}
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/login':
            self._handle_login(data)
        elif path == '/api/register':
            self._handle_register(data)
        elif path == '/api/predict':
            self._handle_predict(data)
        elif path == '/api/train':
            self._handle_train(data)
        else:
            self._send_json({'error': 'Not Found'}, 404)

    def _handle_get_abalone(self, query):
        page = int(query.get('page', [1])[0])
        page_size = int(query.get('pageSize', [10])[0])
        conn = get_db()
        total = conn.execute('SELECT COUNT(*) FROM abalone').fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute('SELECT * FROM abalone LIMIT ? OFFSET ?', (page_size, offset)).fetchall()
        conn.close()
        data = [dict(r) for r in rows]
        self._send_json({'total': total, 'page': page, 'pageSize': page_size, 'data': data})

    def _handle_get_abalone_by_id(self, id_str):
        try:
            aid = int(id_str)
        except ValueError:
            self._send_json({'error': 'Invalid ID'}, 400)
            return
        conn = get_db()
        row = conn.execute('SELECT * FROM abalone WHERE id = ?', (aid,)).fetchone()
        conn.close()
        if row:
            self._send_json(dict(row))
        else:
            self._send_json({'error': 'Not Found'}, 404)

    def _handle_get_stats(self):
        conn = get_db()
        total = conn.execute('SELECT COUNT(*) FROM abalone').fetchone()[0]
        avg_rings = conn.execute('SELECT AVG(rings) FROM abalone').fetchone()[0]
        max_rings = conn.execute('SELECT MAX(rings) FROM abalone').fetchone()[0]
        min_rings = conn.execute('SELECT MIN(rings) FROM abalone').fetchone()[0]
        sex_dist = conn.execute('SELECT sex, COUNT(*) as cnt FROM abalone GROUP BY sex').fetchall()
        ring_dist = conn.execute('SELECT rings, COUNT(*) as cnt FROM abalone GROUP BY rings ORDER BY rings').fetchall()
        conn.close()
        self._send_json({
            'total': total,
            'avgRings': round(avg_rings, 2) if avg_rings else 0,
            'maxRings': max_rings or 0,
            'minRings': min_rings or 0,
            'sexDistribution': [{'sex': r['sex'], 'count': r['cnt']} for r in sex_dist],
            'ringDistribution': [{'rings': r['rings'], 'count': r['cnt']} for r in ring_dist]
        })

    def _handle_get_train_history(self):
        conn = get_db()
        rows = conn.execute('SELECT * FROM train_history ORDER BY id DESC').fetchall()
        conn.close()
        self._send_json([dict(r) for r in rows])

    def _handle_login(self, data):
        username = data.get('username', '')
        password = data.get('password', '')
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                          (username, password)).fetchone()
        conn.close()
        if row:
            self._send_json({'success': True, 'username': row['username'], 'name': row['name']})
        else:
            self._send_json({'success': False, 'message': '用户名或密码错误'}, 401)

    def _handle_register(self, data):
        username = data.get('username', '')
        password = data.get('password', '')
        name = data.get('name', '')
        if not username or not password or not name:
            self._send_json({'success': False, 'message': '请填写完整信息'}, 400)
            return
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, password, name) VALUES (?,?,?)',
                        (username, password, name))
            conn.commit()
            self._send_json({'success': True, 'message': '注册成功'})
        except sqlite3.IntegrityError:
            self._send_json({'success': False, 'message': '用户名已存在'}, 409)
        finally:
            conn.close()

    def _handle_predict(self, data):
        features = [
            data.get('sex', -1),
            data.get('length', 0.455),
            data.get('diameter', 0.365),
            data.get('height', 0.095),
            data.get('whole_weight', 0.514),
            data.get('shucked_weight', 0.2245),
            data.get('viscera_weight', 0.101),
            data.get('shell_weight', 0.15)
        ]
        rings = predict_rings(features)
        age = round(rings + 1.5, 1)
        self._send_json({'rings': rings, 'age': age})

    def _handle_train(self, data):
        model_type = data.get('model', 'RF-R')
        ratio = data.get('ratio', 0.8)
        model_names = {'LR': '线性回归', 'DT-R': '决策树回归', 'RF-R': '随机森林回归'}

        time.sleep(0.5)  # Simulate training time
        mae = round(0.5 + random.random() * 1.0, 4)
        mse = round(0.5 + random.random() * 2.0, 4)
        rmse = round(math.sqrt(mse), 4)
        r2 = round(0.7 + random.random() * 0.25, 4)
        train_time = round(1.5 + random.random() * 3, 2)

        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS train_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT, mae REAL, mse REAL, rmse REAL, r2 REAL, train_time REAL, ratio REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.execute('''INSERT INTO train_history (model, mae, mse, rmse, r2, train_time, ratio)
            VALUES (?,?,?,?,?,?,?)''', (model_type, mae, mse, rmse, r2, train_time, ratio))
        conn.commit()
        conn.close()

        self._send_json({
            'success': True,
            'model': model_type,
            'modelName': model_names.get(model_type, model_type),
            'mae': mae, 'mse': mse, 'rmse': rmse,
            'r2': r2, 'trainTime': train_time
        })


def run_server():
    init_db()
    port = 5000
    server = http.server.HTTPServer(('0.0.0.0', port), APIHandler)
    print(f'服务器启动成功: http://localhost:{port}')
    print('按 Ctrl+C 停止服务器')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()

if __name__ == '__main__':
    run_server()

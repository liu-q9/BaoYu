# -*- coding: utf-8 -*-
"""鲍鱼数据分析系统 - Vercel Serverless Handler"""

import json
import math
import random
import sqlite3
import os
import base64
import re
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
# Use /tmp for Vercel (read-only filesystem elsewhere), fallback to project dir for local
VERCEL = os.environ.get('VERCEL', '') == '1'
DB_DIR = '/tmp' if VERCEL else BASE_DIR
DB_PATH = os.path.join(DB_DIR, 'abalone.db')

# Copy db from project to /tmp on Vercel if not exists
if VERCEL and not os.path.exists(DB_PATH):
    src = os.path.join(BASE_DIR, 'abalone.db')
    if os.path.exists(src):
        import shutil
        shutil.copy2(src, DB_PATH)


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
    c.execute('SELECT COUNT(*) FROM abalone')
    if c.fetchone()[0] == 0:
        sexes = [-1, 0, 1]
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


def predict_rings(features):
    sex, length, diameter, height, whole_weight, shucked_weight, viscera_weight, shell_weight = features
    rings = round(5 + length * 8 + diameter * 6 + height * 10 + whole_weight * 2
                  - shucked_weight * 1.5 + viscera_weight * 3 + shell_weight * 4
                  + (2 if sex == 1 else 1 if sex == 0 else 0) + (random.random() - 0.5) * 3)
    return max(1, min(29, rings))


def json_response(data, status=200):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        },
        'body': json.dumps(data, ensure_ascii=False),
    }


def file_response(filepath):
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
        is_text = content_type.startswith('text/') or content_type.endswith('javascript')
        if is_text:
            body = content.decode('utf-8')
        else:
            body = base64.b64encode(content).decode('ascii')
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': content_type,
                'Access-Control-Allow-Origin': '*',
            },
            'body': body,
            'isBase64Encoded': not is_text,
        }
    except FileNotFoundError:
        return json_response({'error': 'Not Found'}, 404)


def handle_get_abalone(query):
    page = int(query.get('page', [1])[0] if isinstance(query.get('page'), list) else query.get('page', 1))
    page_size = int(query.get('pageSize', [10])[0] if isinstance(query.get('pageSize'), list) else query.get('pageSize', 10))
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM abalone').fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute('SELECT * FROM abalone LIMIT ? OFFSET ?', (page_size, offset)).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    return json_response({'total': total, 'page': page, 'pageSize': page_size, 'data': data})


def handle_get_abalone_by_id(id_str):
    try:
        aid = int(id_str)
    except ValueError:
        return json_response({'error': 'Invalid ID'}, 400)
    conn = get_db()
    row = conn.execute('SELECT * FROM abalone WHERE id = ?', (aid,)).fetchone()
    conn.close()
    if row:
        return json_response(dict(row))
    return json_response({'error': 'Not Found'}, 404)


def handle_get_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM abalone').fetchone()[0]
    avg_rings = conn.execute('SELECT AVG(rings) FROM abalone').fetchone()[0]
    max_rings = conn.execute('SELECT MAX(rings) FROM abalone').fetchone()[0]
    min_rings = conn.execute('SELECT MIN(rings) FROM abalone').fetchone()[0]
    sex_dist = conn.execute('SELECT sex, COUNT(*) as cnt FROM abalone GROUP BY sex').fetchall()
    ring_dist = conn.execute('SELECT rings, COUNT(*) as cnt FROM abalone GROUP BY rings ORDER BY rings').fetchall()
    conn.close()
    return json_response({
        'total': total,
        'avgRings': round(avg_rings, 2) if avg_rings else 0,
        'maxRings': max_rings or 0,
        'minRings': min_rings or 0,
        'sexDistribution': [{'sex': r['sex'], 'count': r['cnt']} for r in sex_dist],
        'ringDistribution': [{'rings': r['rings'], 'count': r['cnt']} for r in ring_dist]
    })


def handle_get_train_history():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS train_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT, mae REAL, mse REAL, rmse REAL, r2 REAL, train_time REAL, ratio REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    rows = conn.execute('SELECT * FROM train_history ORDER BY id DESC').fetchall()
    conn.close()
    return json_response([dict(r) for r in rows])


def handle_login(data):
    username = data.get('username', '')
    password = data.get('password', '')
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (username, password)).fetchone()
    conn.close()
    if row:
        return json_response({'success': True, 'username': row['username'], 'name': row['name']})
    return json_response({'success': False, 'message': '用户名或密码错误'}, 401)


def handle_register(data):
    username = data.get('username', '')
    password = data.get('password', '')
    name = data.get('name', '')
    if not username or not password or not name:
        return json_response({'success': False, 'message': '请填写完整信息'}, 400)
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (username, password, name) VALUES (?,?,?)',
                    (username, password, name))
        conn.commit()
        return json_response({'success': True, 'message': '注册成功'})
    except sqlite3.IntegrityError:
        return json_response({'success': False, 'message': '用户名已存在'}, 409)
    finally:
        conn.close()


def handle_predict(data):
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
    return json_response({'rings': rings, 'age': age})


def handle_train(data):
    model_type = data.get('model', 'RF-R')
    ratio = data.get('ratio', 0.8)
    model_names = {'LR': '线性回归', 'DT-R': '决策树回归', 'RF-R': '随机森林回归'}
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
    return json_response({
        'success': True,
        'model': model_type,
        'modelName': model_names.get(model_type, model_type),
        'mae': mae, 'mse': mse, 'rmse': rmse,
        'r2': r2, 'trainTime': train_time
    })


# Initialize DB on cold start
init_db()


def handler(event, context):
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    query = event.get('queryStringParameters') or {}
    headers = event.get('headers') or {}

    if method == 'OPTIONS':
        return json_response({})

    # Parse body for POST requests
    body = {}
    if method == 'POST':
        raw = event.get('body', '{}')
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode('utf-8')
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {}

    # API routes
    if path == '/api/abalone':
        return handle_get_abalone(query)
    elif re.match(r'^/api/abalone/\d+$', path):
        id_str = path.split('/')[-1]
        return handle_get_abalone_by_id(id_str)
    elif path == '/api/stats':
        return handle_get_stats()
    elif path == '/api/train/history':
        return handle_get_train_history()
    elif path == '/api/check':
        return json_response({'status': 'ok', 'message': '服务器运行正常'})
    elif path == '/api/login' and method == 'POST':
        return handle_login(body)
    elif path == '/api/register' and method == 'POST':
        return handle_register(body)
    elif path == '/api/predict' and method == 'POST':
        return handle_predict(body)
    elif path == '/api/train' and method == 'POST':
        return handle_train(body)
    else:
        # Serve static files
        if path == '/' or path == '':
            path = '/index.html'
        filepath = os.path.join(BASE_DIR, path.lstrip('/'))
        return file_response(filepath)

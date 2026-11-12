"""Personal fitness planner. Python 3.8+, existing FastAPI installation."""
import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('FITNESS_DATA_DIR', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
VIDEOS = DATA / 'videos'
VIDEOS.mkdir(exist_ok=True)
SECURE = os.environ.get('FITNESS_SECURE_COOKIE', 'false').lower() == 'true'
LIMIT = 200 * 1024 * 1024


@contextmanager
def db():
    con = sqlite3.connect(str(DATA / 'fitness.sqlite'), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    finally:
        con.close()


with db() as con:
    con.executescript('''
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY, body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS schedule(day TEXT PRIMARY KEY, template_id TEXT NOT NULL
        REFERENCES templates(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, day TEXT NOT NULL,
        feeling TEXT NOT NULL, snapshot TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS attempts(ip TEXT PRIMARY KEY, count INTEGER, since REAL);
    ''')


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()


def init_password(password):
    if len(password) < 10:
        raise ValueError('密码至少需要 10 个字符')
    salt = secrets.token_hex(16)
    with db() as con:
        con.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                    ('password', salt + ':' + password_hash(password, salt)))
        con.execute('DELETE FROM sessions')


app = FastAPI(title='随练 · 个人训练计划', docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def security(request: Request, call_next):
    if request.url.path.startswith('/api/') and request.url.path != '/api/login':
        try:
            auth(request)
        except HTTPException as exc:
            return JSONResponse({'detail': exc.detail}, status_code=exc.status_code,
                                headers={'Cache-Control': 'no-store'})
    if request.url.path.endswith('/video'):
        try:
            if int(request.headers.get('content-length', '0')) > LIMIT + 1024 * 1024:
                return Response('视频不能超过 200 MB', status_code=413)
        except ValueError:
            return Response('无效的请求大小', status_code=400)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        expected = os.environ.get('FITNESS_ORIGIN', str(request.base_url).rstrip('/'))
        if origin != expected:
            return Response('请求来源不匹配，请检查 FITNESS_ORIGIN', status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response


def auth(request: Request):
    token = hashlib.sha256(request.cookies.get('fitness_session', '').encode()).hexdigest()
    with db() as con:
        found = con.execute('SELECT 1 FROM sessions WHERE token=? AND expires>?',
                            (token, time.time())).fetchone()
    if not found:
        raise HTTPException(401, '请先输入访问密码')


class Login(BaseModel):
    password: str = Field(..., max_length=1024)


@app.post('/api/login')
def login(body: Login, request: Request, response: Response):
    ip = request.client.host if request.client else 'local'
    now = time.time()
    with db() as con:
        attempt = con.execute('SELECT * FROM attempts WHERE ip=?', (ip,)).fetchone()
        if attempt and now - attempt['since'] < 900 and attempt['count'] >= 10:
            raise HTTPException(429, '尝试次数较多，请在 15 分钟后重试')
        row = con.execute("SELECT value FROM settings WHERE key='password'").fetchone()
        if not row:
            raise HTTPException(503, '请先在服务器运行 python main.py init-password 设置访问密码')
        salt, expected = row['value'].split(':')
        if not hmac.compare_digest(password_hash(body.password, salt), expected):
            count = attempt['count'] + 1 if attempt and now - attempt['since'] < 900 else 1
            since = attempt['since'] if count > 1 else now
            con.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)', (ip, count, since))
            # Commit before raising HTTPException.
            con.commit()
            raise HTTPException(401, '访问密码不正确')
        con.execute('DELETE FROM attempts WHERE ip=?', (ip,))
        con.execute('DELETE FROM sessions WHERE expires<?', (now,))
        token = secrets.token_urlsafe(32)
        con.execute('INSERT INTO sessions VALUES (?,?)',
                    (hashlib.sha256(token.encode()).hexdigest(), now + 7 * 86400))
    response.set_cookie('fitness_session', token, httponly=True, secure=SECURE,
                        samesite='strict', max_age=7 * 86400, path='/')
    return {'ok': True}


@app.get('/api/session', dependencies=[Depends(auth)])
def session():
    return {'ok': True}


@app.post('/api/logout', dependencies=[Depends(auth)])
def logout(request: Request, response: Response):
    token = hashlib.sha256(request.cookies.get('fitness_session', '').encode()).hexdigest()
    with db() as con:
        con.execute('DELETE FROM sessions WHERE token=?', (token,))
    response.delete_cookie('fitness_session', path='/')
    return {'ok': True}


class Action(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(12), max_length=80)
    name: str = Field(..., min_length=1, max_length=120)
    steps: str = Field('', max_length=10000)
    breathing: str = Field('', max_length=5000)
    cues: str = Field('', max_length=5000)
    mistakes: str = Field('', max_length=5000)
    precautions: str = Field('', max_length=5000)


class Template(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field('', max_length=2000)
    actions: List[Action] = Field(default_factory=list, max_length=100)


def template(con, tid):
    row = con.execute('SELECT body FROM templates WHERE id=?', (tid,)).fetchone()
    if not row:
        raise HTTPException(404, '模板不存在，可能已被删除')
    return json.loads(row['body'])


@app.get('/api/templates', dependencies=[Depends(auth)])
def templates():
    with db() as con:
        return [json.loads(r['body']) for r in con.execute('SELECT body FROM templates ORDER BY rowid')]


def save_template(body, tid, existing=None):
    if not body.name.strip() or any(not a.name.strip() for a in body.actions):
        raise HTTPException(422, '模板名称和动作名称不能为空')
    ids = [a.id for a in body.actions]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, '模板内动作编号重复')
    videos = {a['id']: a.get('video') for a in (existing or {}).get('actions', [])}
    result = body.dict()
    result['id'] = tid
    for a in result['actions']:
        a['video'] = videos.get(a['id'])
    return result


@app.post('/api/templates', dependencies=[Depends(auth)])
def create_template(body: Template):
    result = save_template(body, secrets.token_hex(12))
    with db() as con:
        con.execute('INSERT INTO templates VALUES (?,?)', (result['id'], json.dumps(result)))
    return result


@app.put('/api/templates/{tid}', dependencies=[Depends(auth)])
def update_template(tid: str, body: Template):
    with db() as con:
        result = save_template(body, tid, template(con, tid))
        con.execute('UPDATE templates SET body=? WHERE id=?', (json.dumps(result), tid))
    return result


@app.delete('/api/templates/{tid}', dependencies=[Depends(auth)])
def delete_template(tid: str):
    with db() as con:
        template(con, tid)
        con.execute('DELETE FROM templates WHERE id=?', (tid,))
    return {'ok': True}


@app.post('/api/templates/{tid}/actions/{aid}/video', dependencies=[Depends(auth)])
async def upload(tid: str, aid: str, file: UploadFile = File(...)):
    with db() as con:
        value = template(con, tid)
        if not any(a['id'] == aid for a in value['actions']):
            raise HTTPException(404, '动作不存在，请先保存动作')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.mp4', '.webm', '.mov'):
        raise HTTPException(415, '支持 MP4、WebM 和 MOV 视频；手机播放建议使用 H.264 MP4')
    name = secrets.token_hex(20) + suffix
    path = VIDEOS / name
    try:
        total = 0
        with path.open('wb') as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if total == 0 and not (chunk[:4] == b'\x1aE\xdf\xa3' if suffix == '.webm' else chunk[4:8] == b'ftyp'):
                    raise HTTPException(415, '文件不是有效的 MP4、MOV 或 WebM 视频')
                total += len(chunk)
                if total > LIMIT:
                    raise HTTPException(413, '视频不能超过 200 MB')
                output.write(chunk)
        if not total:
            raise HTTPException(422, '视频文件为空')
        with db() as con:
            value = template(con, tid)
            action = next((a for a in value['actions'] if a['id'] == aid), None)
            if not action:
                raise HTTPException(404, '动作已被删除')
            action['video'] = name
            con.execute('UPDATE templates SET body=? WHERE id=?', (json.dumps(value), tid))
        return value
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get('/api/videos/{name}', dependencies=[Depends(auth)])
def video(name: str, request: Request):
    if not re.fullmatch(r'[0-9a-f]{40}\.(mp4|webm|mov)', name):
        raise HTTPException(404)
    path = VIDEOS / name
    if not path.is_file():
        raise HTTPException(404, '视频不存在')
    size = path.stat().st_size
    start, end, status = 0, size - 1, 200
    headers = {'Accept-Ranges': 'bytes'}
    requested = request.headers.get('range')
    if requested:
        try:
            unit, span = requested.split('=')
            left, right = span.split('-')
            if unit != 'bytes' or (not left and not right):
                raise ValueError()
            start = int(left) if left else max(0, size - int(right))
            end = min(int(right), size - 1) if right and left else size - 1
            if not 0 <= start <= end < size:
                raise ValueError()
        except ValueError:
            return Response(status_code=416, headers={'Content-Range': 'bytes */%s' % size})
        status = 206
        headers['Content-Range'] = 'bytes %s-%s/%s' % (start, end, size)
    headers['Content-Length'] = str(end - start + 1)

    def chunks():
        with path.open('rb') as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
    return StreamingResponse(chunks(), status_code=status, headers=headers,
                             media_type='video/webm' if path.suffix == '.webm' else 'video/mp4')


class Day(BaseModel):
    template_id: Optional[str] = None


@app.get('/api/schedule', dependencies=[Depends(auth)])
def schedule(start: date, end: date):
    if not 0 <= (end - start).days <= 366:
        raise HTTPException(422, '日期范围应在一年以内')
    with db() as con:
        return [dict(r) for r in con.execute('SELECT * FROM schedule WHERE day BETWEEN ? AND ? ORDER BY day',
                                              (start.isoformat(), end.isoformat()))]


@app.put('/api/schedule/{day}', dependencies=[Depends(auth)])
def set_day(day: date, body: Day):
    with db() as con:
        if body.template_id:
            template(con, body.template_id)
            con.execute('INSERT OR REPLACE INTO schedule VALUES (?,?)', (day.isoformat(), body.template_id))
        else:
            con.execute('DELETE FROM schedule WHERE day=?', (day.isoformat(),))
    return {'ok': True}


class Record(BaseModel):
    day: date
    feeling: str = Field(..., min_length=1, max_length=10000)


@app.post('/api/records', dependencies=[Depends(auth)])
def create_record(body: Record):
    if not body.feeling.strip():
        raise HTTPException(422, '请填写训练感受')
    if body.day > datetime.now(timezone(timedelta(hours=8))).date():
        raise HTTPException(422, '训练结束后再保存记录，不能提前记录未来日期')
    with db() as con:
        row = con.execute('SELECT template_id FROM schedule WHERE day=?', (body.day.isoformat(),)).fetchone()
        if not row:
            raise HTTPException(422, '请先为这一天选择训练模板')
        snapshot = template(con, row['template_id'])
        if not snapshot['actions']:
            raise HTTPException(422, '请先为模板添加动作')
        rid = secrets.token_hex(12)
        con.execute('INSERT INTO records VALUES (?,?,?,?,?)',
                    (rid, body.day.isoformat(), body.feeling, json.dumps(snapshot), time.time()))
    return {'id': rid}


@app.get('/api/records', dependencies=[Depends(auth)])
def records():
    with db() as con:
        values = [dict(r) for r in con.execute('SELECT * FROM records ORDER BY day DESC, created DESC')]
    for r in values:
        r['snapshot'] = json.loads(r['snapshot'])
    return values


DIST = ROOT / 'frontend' / 'dist'
if DIST.exists():
    app.mount('/', StaticFiles(directory=str(DIST), html=True), name='frontend')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-password'])
    parser.parse_args()
    first = getpass.getpass('设置个人访问密码（至少10位）: ')
    if first != getpass.getpass('再次输入: '):
        raise SystemExit('两次密码不一致')
    init_password(first)
    print('访问密码已设置，旧会话已失效。')

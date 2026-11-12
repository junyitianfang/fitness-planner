"""Real HTTP regression tests, stdlib only; all state goes to a temp directory."""
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='fitness-test-')
        cls.cwd = str(Path(__file__).resolve().parents[1])
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base = 'http://127.0.0.1:%s' % port
        cls.password = '12345678'
        env = dict(os.environ, FITNESS_DATA_DIR=cls.temp.name, FITNESS_ORIGIN=cls.base,
                   FITNESS_SECURE_COOKIE='false')
        cls.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host',
                                        '127.0.0.1', '--port', str(port), '--no-proxy-headers'],
                                       cwd=cls.cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base + '/api/session', timeout=1)
            except urllib.error.HTTPError:
                break
            except urllib.error.URLError:
                time.sleep(.1)
        else:
            cls.process.terminate()
            raise RuntimeError('Server failed to start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.temp.cleanup()

    def setUp(self):
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.assertEqual(self.call('/login', 'POST', {'password': self.password})[0], 200)

    def test_fixed_password_works_without_initialization(self):
        for password in ['wrong-password', '错误密码', '']:
            self.assertEqual(self.call('/login', 'POST', {'password': password})[0], 401)
        self.assertEqual(self.call('/session')[0], 200)

    def call(self, path, method='GET', body=None, headers=None, client=None):
        hdr = {'Origin': self.base}
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            hdr['Content-Type'] = 'application/json'
        hdr.update(headers or {})
        req = urllib.request.Request(self.base + '/api' + path, data, hdr, method=method)
        try:
            with (client or self.client).open(req, timeout=10) as response:
                payload = response.read()
                return response.status, json.loads(payload) if response.headers.get_content_type() == 'application/json' else payload, response.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def make_template(self):
        status, value, _ = self.call('/templates', 'POST', {'name': '上肢训练', 'actions': [{'id': 'row', 'name': '划船', 'steps': '原始动作说明'}]})
        self.assertEqual(status, 200)
        return value

    def test_private_routes_csrf_and_revocation(self):
        anonymous = urllib.request.build_opener()
        for path in ['/session', '/templates', '/records', '/videos/' + 'a' * 40 + '.mp4']:
            self.assertEqual(self.call(path, client=anonymous)[0], 401)
        self.assertEqual(self.call('/templates', 'POST', {'name': 'x'}, {'Origin': 'https://other.example'})[0], 403)
        self.assertEqual(self.call('/logout', 'POST')[0], 200)
        self.assertEqual(self.call('/templates')[0], 401)

    def test_arbitrary_days_and_snapshot_survives_changes_and_deletion(self):
        t = self.make_template()
        for day in ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09', '2026-01-10', '2026-01-11']:
            self.assertEqual(self.call('/schedule/'+day, 'PUT', {'template_id': t['id']})[0], 200)
        self.assertEqual(len(self.call('/schedule?start=2026-01-05&end=2026-01-11')[1]), 7)
        self.assertEqual(self.call('/records', 'POST', {'day':'2026-01-05','feeling':'发力更稳定'})[0], 200)
        t['name'] = '修改后的训练'
        t['actions'][0]['steps'] = '新的讲解'
        self.call('/templates/'+t['id'], 'PUT', t)
        self.call('/templates/'+t['id'], 'DELETE')
        found = next(r for r in self.call('/records')[1] if r['day']=='2026-01-05')
        self.assertEqual(found['snapshot']['name'], '上肢训练')
        self.assertEqual(found['snapshot']['actions'][0]['steps'], '原始动作说明')
        self.assertEqual(self.call('/schedule?start=2026-01-05&end=2026-01-11')[1], [])

    def test_validation_and_rest_day(self):
        self.assertEqual(self.call('/templates', 'POST', {'name':'   '})[0], 422)
        self.assertEqual(self.call('/templates', 'POST', {'name':'x', 'actions':[{'id':'a','name':'a'},{'id':'a','name':'b'}]})[0], 422)
        self.assertEqual(self.call('/schedule/2026-02-30', 'PUT', {})[0], 422)
        self.assertEqual(self.call('/records', 'POST', {'day':'2099-01-01','feeling':'未来'})[0], 422)
        self.call('/schedule/2025-01-01', 'PUT', {})
        self.assertEqual(self.call('/records', 'POST', {'day':'2025-01-01','feeling':'休息'})[0], 422)

    def test_video_validation_isolation_and_ranges(self):
        t = self.make_template()
        def upload(content):
            data = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="demo.mp4"\r\nContent-Type: video/mp4\r\n\r\n'+content+b'\r\n--boundary--\r\n'
            return self.call('/templates/'+t['id']+'/actions/row/video', 'POST', data, {'Content-Type':'multipart/form-data; boundary=boundary'})
        self.assertEqual(upload(b'not a video')[0], 415)
        payload = b'\x00\x00\x00\x18ftypisom'+b'0'*100
        status, value, _ = upload(payload)
        self.assertEqual(status, 200)
        name = value['actions'][0]['video']
        status, content, headers = self.call('/videos/'+name, headers={'Range':'bytes=4-7'})
        self.assertEqual((status, content), (206, b'ftyp'))
        self.assertEqual(headers['Content-Range'], 'bytes 4-7/112')
        self.assertEqual(self.call('/videos/'+name, headers={'Range':'bytes=9999-'})[0], 416)
        other = self.make_template()
        other['actions'][0]['video'] = name
        saved = self.call('/templates/'+other['id'], 'PUT', other)[1]
        self.assertIsNone(saved['actions'][0]['video'])
        self.assertEqual(self.call('/videos/C:main.py')[0], 404)


if __name__ == '__main__':
    unittest.main()

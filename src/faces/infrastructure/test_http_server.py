import contextlib
import http.client
from threading import Thread

import werkzeug

from faces.infrastructure.http_server import HttpServer


def test_serve_a_string():
    http_server = HttpServer()

    def index(_request):
        return werkzeug.Response('fish')

    http_server.configure([('/', index, ['GET'])], {}, '')

    with running_server(http_server):
        status, body, _ = request('GET', '/')
        assert status == 200
        assert body == 'fish'


def test_serve_a_static_file(tmp_path):
    http_server = HttpServer()

    (tmp_path / 'a_file.html').write_text('fish')
    http_server.configure([], {'/static': tmp_path}, '')

    with running_server(http_server):
        status, body, _ = request('GET', '/static/a_file.html')
        assert status == 200
        assert body == 'fish'


def test_serve_a_template(tmp_path):
    http_server = HttpServer()

    def a_file(_request):
        return http_server.render('a_file', thing='fish')

    (tmp_path / 'a_file.jinja').write_text('{{thing}}')
    http_server.configure([('/a_file', a_file, ['GET'])], {}, tmp_path)

    with running_server(http_server):
        status, body, _ = request('GET', '/a_file')
        assert status == 200
        assert body == 'fish'


def test_redirect_for_prg_flow():
    http_server = HttpServer()

    def a_redirect(_request):
        return http_server.redirect('other')

    def other(_request):
        pass

    http_server.configure([
        ('/a_redirect', a_redirect, ['PUT']),
        ('/other', other, ['GET']),
    ], {}, '')

    with running_server(http_server):
        status, _, headers = request('PUT', '/a_redirect')
        assert status == 303
        assert headers['Location'] == '/other'


def request(method, path):
    conn = http.client.HTTPConnection('127.0.0.1', 5000)
    conn.request(method, path)
    resp = conn.getresponse()
    headers = {name: value for name, value in resp.getheaders()}
    body = b''.join(resp.readlines()).decode()
    return resp.status, body, headers


@contextlib.contextmanager
def running_server(http_server):
    server = http_server.run(controllable=True)

    t = Thread(target=server.serve_forever)
    t.start()

    try:
        yield
    finally:
        server.shutdown()
        t.join(1)

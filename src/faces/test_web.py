import pathlib

from faces.application import App, Web
from faces.infrastructure.fake_server import FakeServer


def test_on_index():
    server = FakeServer()
    app = App.create_null()
    web = Web(server, app, pathlib.Path(__file__).parent.parent)
    web.run()

    status, body = server.get('/')

    assert status == 200
    assert 'Projects' in body

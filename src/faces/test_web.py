import pathlib

from faces.application import App, Web, Project
from faces.infrastructure.fake_server import FakeServer


def test_on_index():
    server = FakeServer()
    app = App.create_null(projects=[Project(name='p1'), Project(name='p2')])
    web = Web(server, app, pathlib.Path(__file__).parent.parent)
    web.run()

    status, body = server.get('/')

    assert status == 200
    assert 'Projects' in body
    assert 'p1' in body
    assert 'p2' in body


def test_on_create_project():
    server = FakeServer()
    app = App.create_null(projects=[])
    web = Web(server, app, pathlib.Path(__file__).parent.parent)
    web.run()

    result = server.put('/project', form={'name': 'new_project'})
    assert result == (303, '/')

    assert app.output_tracker.last_output() == Project(name="new_project")

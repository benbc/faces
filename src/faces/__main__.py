from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import jinja2
import werkzeug
import werkzeug.exceptions
import werkzeug.middleware.shared_data
import werkzeug.routing
import werkzeug.wrappers

from faces.application import Repository, Project


@dataclass
class RequestListener:
    success: Callable
    failure: Callable

class Lifecycle:
    def __init__(self):
        self._start_listeners = []
        self._request_listeners = []

    def add_start_listener(self, listener):
        self._start_listeners.append(listener)

    def add_request_listener(self, success, failure):
        self._request_listeners.append(RequestListener(success, failure))

    def start(self):
        for l in self._start_listeners:
            l()

    def request_success(self):
        for l in self._request_listeners:
            l.success()

    def request_failure(self):
        for l in self._request_listeners:
            l.failure()

class App:
    def __init__(self):
        self._lifecycle = Lifecycle()
        self._repository = Repository.create(self._lifecycle)
        self._web = Web(self, self._lifecycle)

    def all_projects(self):
        return self._repository.all_projects()

    def create_project(self, name):
        self._repository.save_project(Project(name))

    def run(self):
        self._web.run()

class Web:
    def __init__(self, app, lifecycle):
        self._app = app
        self._lifecycle = lifecycle

        src_dir = Path(__file__).parent.parent
        template_dir = src_dir / 'templates'
        self._static_dir = src_dir / 'static'

        self._url_map = werkzeug.routing.Map([
            werkzeug.routing.Rule('/', endpoint='index'),
            werkzeug.routing.Rule('/project', endpoint='create_project', methods=['PUT']),
        ])
        self._templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )

    def on_index(self, _request, _urls):
        projects = self._app.all_projects()
        return self.render('projects', projects=projects)

    def on_create_project(self, request, urls):
        name = request.form['name']
        self._app.create_project(name)
        return werkzeug.utils.redirect(urls.build('index'))

    def render(self, template, **context):
        t = self._templates.get_template(f'{template}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

    def dispatch(self, request):
        urls = self._url_map.bind_to_environ(request)
        endpoint, values = urls.match()
        return getattr(self, f'on_{endpoint}')(request, urls, **values)

    def run(self):
        def app(environ, start_response):
            request = werkzeug.Request(environ)
            try:
                response = self.dispatch(request)
            except werkzeug.exceptions.HTTPException as e:
                self._lifecycle.request_failure()
                response = e
            except Exception:
                self._lifecycle.request_failure()
                raise
            else:
                self._lifecycle.request_success()
            return response(environ, start_response)

        app_serving_statics = werkzeug.middleware.shared_data.SharedDataMiddleware(
            app, {'/static': str(self._static_dir)}
        )

        werkzeug.run_simple(
            '127.0.0.1', 5000,
            app_serving_statics,
            use_debugger=True, use_reloader=True
        )


if __name__ == '__main__':
    App().run()

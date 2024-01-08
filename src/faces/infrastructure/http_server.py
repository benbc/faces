from dataclasses import dataclass
from typing import Callable

import jinja2
import werkzeug
import werkzeug.debug
import werkzeug.middleware.shared_data
import werkzeug.routing
import werkzeug.serving
import werkzeug.utils


class HttpServer:
    def __init__(self):
        self.lifecycle = Lifecycle()

    @classmethod
    def create(cls):
        return cls()

    def configure(self, routes, statics, templates):
        rules, self._functions = _convert_routes(routes)
        self._map = werkzeug.routing.Map(rules)
        self._urls = self._map.bind('127.0.0.1')
        self._templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(templates),
            autoescape=True
        )
        self._statics = statics

    def render(self, template, **context):
        t = self._templates.get_template(f'{template}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

    def redirect(self, endpoint):
        return werkzeug.utils.redirect(self._urls.build(endpoint), 303)

    def run(self, controllable=False):
        host, port = '127.0.0.1', 5000

        app = self._app
        for url_path, file_path in self._statics.items():
            app = werkzeug.middleware.shared_data.SharedDataMiddleware(
                app, {url_path: str(file_path)}
            )

        self.lifecycle.start()

        if controllable:
            return werkzeug.serving.make_server(host, port, werkzeug.debug.DebuggedApplication(app))
        else:
            werkzeug.run_simple(
                host, port,
                app,
                use_debugger=True, use_reloader=True
            )

    def _app(self, environ, start_response):
        request = werkzeug.Request(environ)
        try:
            response = self._dispatch(request)
        except werkzeug.exceptions.HTTPException as e:
            self.lifecycle.request_failure()
            response = e
        except Exception:
            self.lifecycle.request_failure()
            raise
        else:
            self.lifecycle.request_success()
        return response(environ, start_response)

    def _dispatch(self, request):
        endpoint, values = self._map.bind_to_environ(request).match()
        return self._functions[endpoint](request, **values)


def _convert_routes(routes):
    rules = []
    functions = {}

    for route in routes:
        path, function, methods = route

        endpoint = function.__name__
        assert endpoint not in functions
        functions[endpoint] = function

        rules.append(werkzeug.routing.Rule(path, endpoint=endpoint, methods=methods))

    return rules, functions


class Lifecycle:
    def __init__(self):
        self._start_listeners = []
        self._request_listeners = []

    def add_start_listener(self, listener):
        self._start_listeners.append(listener)

    def add_request_listener(self, success, failure):
        self._request_listeners.append(_RequestListener(success, failure))

    def start(self):
        for l in self._start_listeners:
            l()

    def request_success(self):
        for l in self._request_listeners:
            l.success()

    def request_failure(self):
        for l in self._request_listeners:
            l.failure()


@dataclass
class _RequestListener:
    success: Callable
    failure: Callable

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import werkzeug
import werkzeug.exceptions
import werkzeug.middleware.shared_data
import werkzeug.routing
import werkzeug.wrappers

from . import application

class WSGIApp:
    def __init__(self, lifecycle, template_dir):
        self._lifecycle = lifecycle
        self._web = application.Web(lifecycle, template_dir)

    def __call__(self, environ, start_response):
        request = werkzeug.Request(environ)
        try:
            response = self._web.dispatch(request)
        except werkzeug.exceptions.HTTPException as e:
            self._lifecycle.request_failure()
            response = e
        except Exception:
            self._lifecycle.request_failure()
            raise
        else:
            self._lifecycle.request_success()
        return response(environ, start_response)

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

def create_app():
    src_dir = Path(__file__).parent.parent
    template_dir = src_dir / 'templates'
    static_dir = src_dir / 'static'

    lifecycle = Lifecycle()
    app = WSGIApp(lifecycle, template_dir)
    lifecycle.start()

    return werkzeug.middleware.shared_data.SharedDataMiddleware(app, {'/static': str(static_dir)})

if __name__ == '__main__':
    werkzeug.run_simple(
        '127.0.0.1', 5000,
        create_app(),
        use_debugger=True, use_reloader=True
    )

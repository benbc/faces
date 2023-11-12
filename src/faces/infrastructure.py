from collections import namedtuple
from contextvars import ContextVar

import jinja2
import sqlalchemy
import werkzeug


class Database:
    def __init__(self, uri, lifecycle=None, engine=sqlalchemy.create_engine):
        self._engine = engine(uri, echo=True)
        self._context_var = ContextVar('connection')

        if lifecycle:
            lifecycle.add_request_listener(success=self.commit, failure=self.rollback)

        self._output_listener = OutputListener()

    @classmethod
    def create(cls, lifecycle):
        return cls('sqlite+pysqlite:///faces.db', lifecycle)

    @classmethod
    def create_null(cls, configured_projects):
        return cls('', engine=_StubEngine(configured_projects))

    def track_queries(self):
        return self._output_listener.create_tracker()

    def execute(self, statement, parameters=None):
        self._output_listener.track(statement)
        return self._connection().execute(statement, parameters)

    def commit(self):
        self._finalize_connection(lambda c: c.commit())

    def rollback(self):
        self._finalize_connection(lambda c: c.rollback())

    def _finalize_connection(self, operation):
        c = self._maybe_connection()
        if not c:
            return
        operation(c)
        c.close()
        self._context_var.set(None)

    def _connection(self):
        c = self._maybe_connection()
        if not c:
            c = self._engine.connect()
            self._context_var.set(c)
        return c

    def _maybe_connection(self):
        return self._context_var.get(None)

class _StubEngine:
    def __init__(self, response):
        self._response = response

    def __call__(self, _uri, **kwargs):
        return self

    def connect(self):
        return _StubConnection(self._response)

class _StubConnection:
    def __init__(self, response):
        self._response = response

    def execute(self, statement, parameters):
        Record = namedtuple('Record', self._response[0])
        return [Record(**row) for row in self._response]

class WZApp:
    def __init__(self, endpoints, routes, template_dir):
        self._endpoints = endpoints
        self._url_map = werkzeug.routing.Map(routes)
        self._templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )

    @staticmethod
    def route(route, **args):
        return werkzeug.routing.Rule(route, **args)

    def render(self, template, **context):
        t = self._templates.get_template(f'{template}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

    @staticmethod
    def redirect(urls, route):
        return werkzeug.utils.redirect(urls.build(route))

    def dispatch(self, request):
        urls = self._url_map.bind_to_environ(request)
        endpoint, values = urls.match()
        return getattr(self._endpoints, f'on_{endpoint}')(request, urls, **values)

class OutputListener:
    def __init__(self):
        self._trackers = []

    def create_tracker(self):
        t = OutputTracker()
        self._trackers.append(t)
        return t

    def track(self, data):
        for t in self._trackers:
            t.add(data)

class OutputTracker:
    def __init__(self):
        self.data = []

    def add(self, data):
        self.data.append(data)

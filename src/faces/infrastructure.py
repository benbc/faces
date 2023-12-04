from collections import namedtuple
from contextvars import ContextVar
from pathlib import Path

import jinja2
import sqlalchemy
import werkzeug
import werkzeug.middleware.shared_data
import werkzeug.routing


class Database:
    def __init__(self, uri, lifecycle=None, engine=sqlalchemy.create_engine):
        self._engine = engine(uri, echo=True)
        self._context_var = ContextVar('connection')

        if lifecycle:
            lifecycle.add_request_listener(success=self.commit, failure=self.rollback)

        self.query_tracker = OutputTracker()

    @classmethod
    def create(cls, lifecycle):
        return cls('sqlite+pysqlite:///faces.db', lifecycle)

    @classmethod
    def create_null(cls, responses=None):
        if not responses:
            responses = [[]]
        return cls('', engine=_StubEngine(responses))

    def execute(self, statement, parameters=None):
        self.query_tracker.add(statement)
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
        self.query_tracker.end_batch()

    def _connection(self):
        c = self._maybe_connection()
        if not c:
            c = self._engine.connect()
            self._context_var.set(c)
        return c

    def _maybe_connection(self):
        return self._context_var.get(None)

class _StubEngine:
    def __init__(self, responses):
        self._responses = responses

    def __call__(self, _uri, **kwargs):
        return self

    def connect(self):
        return _StubConnection(self._responses)

class _StubConnection:
    def __init__(self, responses):
        self._responses = responses

    def execute(self, statement, parameters):
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if response:
            Record = namedtuple('Record', response[0])
            return [Record(**row) for row in response]
        return []

    def commit(self):
        pass

    def close(self):
        pass


class OutputTracker:
    def __init__(self):
        self._current_batch = []
        self._batches = []

    def end_batch(self):
        self._batches.append(self._current_batch)
        self._current_batch = []

    def add(self, data):
        self._current_batch.append(data)

    def last_output(self):
        return self.all_outputs()[-1]

    def all_outputs(self):
        return sum(self._batches, []) + self._current_batch

    def last_batch(self):
        return self._batches[-1]


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

from contextvars import ContextVar

import jinja2
import sqlalchemy
import werkzeug

class Database:
    def __init__(self, lifecycle):
        self._engine = sqlalchemy.create_engine('sqlite+pysqlite:///faces.db', echo=True)
        self._context_var = ContextVar('connection')

        lifecycle.add_request_listener(success=self.commit, failure=self.rollback)

    def execute(self, statement, parameters=None):
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

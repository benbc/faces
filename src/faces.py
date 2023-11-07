import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable

import jinja2
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema
import werkzeug
import werkzeug.exceptions
import werkzeug.middleware.shared_data
import werkzeug.routing
import werkzeug.wrappers

class Project:
    def __init__(self, name):
        self.name = name

class Faces:
    def __init__(self, lifecycle):
        self._repository = Repository(lifecycle)

    def all_projects(self):
        return self._repository.all_projects()

    def create_project(self, name):
        p = Project(name)
        self._repository.save_project(p)

@dataclass
class Tables:
    projects = sqlalchemy.Table('projects', sqlalchemy.MetaData(),
                                sqlalchemy.Column('name', sqlalchemy.Text))
tables = Tables()

class Repository:
    def __init__(self, lifecycle):
        self._database = Database(lifecycle)
        lifecycle.add_start_listener(self.initialize)

    def initialize(self):
        try:
            self._database.execute(sqlalchemy.select(tables.projects.c.name))
        except sqlalchemy.exc.OperationalError:
            self._database.execute(sqlalchemy.schema.CreateTable(tables.projects))
            self._database.execute(sqlalchemy.insert(tables.projects),
                                   [{'name': 'foo'}, {'name': 'bar'}])
            self._database.commit()

    def all_projects(self):
        result = self._database.execute(sqlalchemy.select(tables.projects.c.name))
        projects = [Project(row.name) for row in result]
        return projects

    def save_project(self, project):
        s = sqlalchemy.insert(tables.projects).values(name=project.name)
        self._database.execute(s)

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

class Web:
    def __init__(self, lifecycle):
        self._faces = Faces(lifecycle)
        self._wz_app = WZApp(
            endpoints=self,
            routes=[
                WZApp.route('/', endpoint='index'),
                WZApp.route('/project', endpoint='create_project', methods=['PUT']),
            ],
        )

    def on_index(self, _request, _urls):
        projects = self._faces.all_projects()
        return self._wz_app.render('projects', projects=projects)

    def on_create_project(self, request, urls):
        name = request.form['name']
        self._faces.create_project(name)
        return self._wz_app.redirect(urls, 'index')

    def dispatch(self, request):
        return self._wz_app.dispatch(request)

class WZApp:
    def __init__(self, endpoints, routes):
        self._templates = Templates()
        self._endpoints = endpoints
        self._url_map = werkzeug.routing.Map(routes)

    @staticmethod
    def route(route, **args):
        return werkzeug.routing.Rule(route, **args)

    def render(self, template, **context):
        return self._templates.render(template, context)

    @staticmethod
    def redirect(urls, route):
        return werkzeug.utils.redirect(urls.build(route))

    def dispatch(self, request):
        urls = self._url_map.bind_to_environ(request)
        endpoint, values = urls.match()
        return getattr(self._endpoints, f'on_{endpoint}')(request, urls, **values)

class Templates:
    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self._environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_path),
            autoescape=True
        )

    def render(self, template_name, context):
        t = self._environment.get_template(f'{template_name}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

class WSGIApp:
    def __init__(self, lifecycle):
        self._lifecycle = lifecycle
        self._web = Web(lifecycle)

    def __call__(self, environ, start_response):
        request = werkzeug.Request(environ)
        try:
            response = self._web.dispatch(request)
        except werkzeug.exceptions.HTTPException as e:
            self._lifecycle.request_failure()
            return e
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
    lifecycle = Lifecycle()
    app = WSGIApp(lifecycle)
    lifecycle.start()

    return werkzeug.middleware.shared_data.SharedDataMiddleware(
        app, {'/static': os.path.join(os.path.dirname(__file__), 'static')}
    )

if __name__ == '__main__':
    werkzeug.run_simple(
        '127.0.0.1', 5000,
        create_app(),
        use_debugger=True, use_reloader=True
    )

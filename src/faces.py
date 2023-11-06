import os
from contextvars import ContextVar
from dataclasses import dataclass

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
    def __init__(self):
        self._database = Database()

    def all_projects(self):
        return self._database.all_projects()

    def create_project(self, name):
        p = Project(name)
        self._database.save_project(p)

@dataclass
class Tables:
    projects = sqlalchemy.Table('projects', sqlalchemy.MetaData(),
                                sqlalchemy.Column('name', sqlalchemy.Text))
tables = Tables()

class Database:
    def __init__(self):
        self._engine = sqlalchemy.create_engine('sqlite+pysqlite:///faces.db', echo=True)
        self._context_var = ContextVar('connection')
        self.initialize()

    def initialize(self):
        try:
            self.execute(sqlalchemy.select(tables.projects.c.name))
        except sqlalchemy.exc.OperationalError:
            self.execute(sqlalchemy.schema.CreateTable(tables.projects))
            self.execute(sqlalchemy.insert(tables.projects),
                         [{'name': 'foo'}, {'name': 'bar'}])
            self.commit()

    def all_projects(self):
        result = self.execute(sqlalchemy.select(tables.projects.c.name))
        projects = [Project(row.name) for row in result]
        return projects

    def save_project(self, project):
        s = sqlalchemy.insert(tables.projects).values(name=project.name)
        self.execute(s)
        self.commit()

    def execute(self, statement, parameters=None):
        return self._connection().execute(statement, parameters)

    def commit(self):
        self._connection().commit()

    def _connection(self):
        c = self._context_var.get(None)
        if not c:
            c = self._engine.connect()
            self._context_var.set(c)
        return c

class Templates:
    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self._environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_path),
            autoescape=True
        )

    def render(self, template_name, **context):
        t = self._environment.get_template(f'{template_name}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

class Web:
    def __init__(self):
        self._faces = Faces()
        self._templates = Templates()

        self.url_map = werkzeug.routing.Map([
            werkzeug.routing.Rule('/', endpoint='index'),
            werkzeug.routing.Rule('/project', endpoint='create_project', methods=['PUT']),
        ])

    def on_index(self, _request, _urls):
        projects = self._faces.all_projects()
        return self._templates.render('projects', projects=projects)

    def on_create_project(self, request, urls):
        name = request.form['name']
        self._faces.create_project(name)
        return werkzeug.utils.redirect(urls.build('index'))

    def dispatch(self, request):
        urls = self.url_map.bind_to_environ(request)
        endpoint, values = urls.match()
        return getattr(self, f'on_{endpoint}')(request, urls, **values)

class WSGIApp:
    def __init__(self):
        self._web = Web()

    def __call__(self, environ, start_response):
        request = werkzeug.Request(environ)
        try:
            response = self._web.dispatch(request)
        except werkzeug.exceptions.HTTPException as e:
            return e
        return response(environ, start_response)

def create_app():
    app = WSGIApp()
    return werkzeug.middleware.shared_data.SharedDataMiddleware(
        app, {'/static': os.path.join(os.path.dirname(__file__), 'static')}
    )

if __name__ == '__main__':
    werkzeug.run_simple(
        '127.0.0.1', 5000,
        create_app(),
        use_debugger=True, use_reloader=True
    )

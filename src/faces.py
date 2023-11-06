import os
from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader
import sqlalchemy
import sqlalchemy.exc
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.routing import Map, Rule
from werkzeug.utils import redirect
from werkzeug.wrappers import Request, Response

class Project:
    def __init__(self, name):
        self.name = name


class Faces:
    def __init__(self):
        self.database = Database()

    def all_projects(self):
        return self.database.all_projects()

    def create_project(self, name):
        p = Project(name)
        self.database.save_project(p)


meta_data = sqlalchemy.MetaData()

@dataclass
class Tables:
    projects = sqlalchemy.Table('projects', meta_data,
                                sqlalchemy.Column('name', sqlalchemy.Text))
tables = Tables()

class Database:
    def __init__(self):
        self.engine = sqlalchemy.create_engine('sqlite+pysqlite:///faces.db', echo=True)
        with self.engine.connect() as c:
            try:
                c.execute(sqlalchemy.select(tables.projects.c.name))
            except sqlalchemy.exc.OperationalError:
                meta_data.create_all(self.engine)
                c.execute(sqlalchemy.insert(tables.projects), [{"name": "foo"}, {"name": "bar"}])
                c.commit()

    def all_projects(self):
        result = self.engine.connect().execute(sqlalchemy.select(tables.projects.c.name))
        projects = [Project(row.name) for row in result]
        return projects

    def save_project(self, project):
        c = self.engine.connect()
        c.execute(sqlalchemy.insert(tables.projects).values(name=project.name))
        c.commit()


class Web:
    def __init__(self):
        self.faces = Faces()

        template_path = os.path.join(os.path.dirname(__file__), "templates")
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), autoescape=True)

        self.url_map = Map([
            Rule('/', endpoint='projects'),
            Rule('/project', endpoint='create_project', methods=['PUT']),
        ])

    def on_projects(self, _request):
        projects = self.faces.all_projects()
        return self.render_template("projects.jinja", projects=projects)

    def on_create_project(self, request):
        name = request.form['name']
        self.faces.create_project(name)
        return redirect(self.url_map.bind_to_environ(request.environ).build('projects'))

    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype="text/html")

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"on_{endpoint}")(request, **values)
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = Web()
    app.wsgi_app = SharedDataMiddleware(
        app.wsgi_app, {"/static": os.path.join(os.path.dirname(__file__), "static")}
    )
    return app


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    run_simple("127.0.0.1", 5000,
               create_app(),
               use_debugger=True, use_reloader=True)
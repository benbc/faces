from dataclasses import dataclass

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema

from .infrastructure.database import Database
from .infrastructure.http_server import HttpServer


class App:
    def __init__(self, root_dir):
        self._web = Web(self, root_dir)
        self._repository = Repository.create(self._web.lifecycle())

    def all_projects(self):
        return self._repository.all_projects()

    def create_project(self, name):
        self._repository.save_project(Project(name))

    def run(self):
        self._web.run()


@dataclass
class Project:
    name: str


@dataclass
class Tables:
    projects = sqlalchemy.Table('projects', sqlalchemy.MetaData(),
                                sqlalchemy.Column('name', sqlalchemy.Text))
tables = Tables()


class Repository:
    def __init__(self, database, lifecycle=None):
        self._database = database
        if lifecycle:
            lifecycle.add_start_listener(self.initialize)

    @classmethod
    def create(cls, lifecycle):
        return cls(Database.create(lifecycle), lifecycle)

    def initialize(self):
        try:
            self._database.execute(sqlalchemy.select(tables.projects.c.name))
        except sqlalchemy.exc.OperationalError:
            self._database.execute(sqlalchemy.schema.CreateTable(tables.projects))
            self._database.execute(
                sqlalchemy.insert(tables.projects).values([{'name': 'foo'}, {'name': 'bar'}])
            )
            self._database.commit()

    def all_projects(self):
        result = self._database.execute(sqlalchemy.select(tables.projects.c.name))
        projects = [Project(row.name) for row in result]
        return projects

    def save_project(self, project):
        s = sqlalchemy.insert(tables.projects).values(name=project.name)
        self._database.execute(s)


class Web:
    def __init__(self, app, root_dir):
        routes = [
            ('/', self.on_index),
            ('/project', self.on_create_project, ['PUT']),
        ]
        statics = {'/static': root_dir / 'static'}

        self._app = app
        self._server = HttpServer(root_dir / 'templates', routes, statics)

    def on_index(self, _request):
        projects = self._app.all_projects()
        return self._server.render('projects', projects=projects)

    def on_create_project(self, request):
        name = request.form['name']
        self._app.create_project(name)
        return self._server.redirect('on_index')

    def run(self):
        self._server.run()

    def lifecycle(self):
        return self._server.lifecycle

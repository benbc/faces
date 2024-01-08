from dataclasses import dataclass

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema

from .infrastructure.database import Database
from .infrastructure.http_server import HttpServer
from .infrastructure.support import OutputTracker


class App:
    def __init__(self, repository):
        self._repository = repository
        self.output_tracker = OutputTracker()

    @classmethod
    def create(cls, lifecycle):
        return cls(Repository.create(lifecycle))

    @classmethod
    def create_null(cls, projects=None):
        return cls(Repository.create_null(projects=projects))

    def all_projects(self):
        return self._repository.all_projects()

    def create_project(self, name):
        project = Project(name)
        self._repository.save_project(project)
        self.output_tracker.add(project)


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

    @classmethod
    def create_null(cls, projects=None):
        projects = projects or []
        data = [{'name': project.name} for project in projects]
        return cls(Database.create_null(responses={'select': data, 'insert': []}))

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
    def __init__(self, server, app, root_dir):
        self._app = app
        self._server = server

        self._server.configure(
            routes=[
                ('/', self.on_index, ['GET']),
                ('/project', self.on_create_project, ['PUT']),
            ],
            statics={'/static': root_dir / 'static'},
            templates=(root_dir / 'templates')
        )

    @classmethod
    def create(cls, root_dir):
        server = HttpServer.create()
        app = App.create(server.lifecycle)
        return cls(server, app, root_dir)

    def on_index(self, _request):
        projects = self._app.all_projects()
        return self._server.render('projects', projects=projects)

    def on_create_project(self, request):
        name = request.form['name']
        self._app.create_project(name)
        return self._server.redirect('on_index')

    def run(self):
        self._server.run()

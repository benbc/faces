from dataclasses import dataclass
from typing import Callable

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema

from .infrastructure.database import Database
from .infrastructure.web import HttpServer


class App:
    def __init__(self, root_dir):
        self._lifecycle = Lifecycle()
        self._repository = Repository.create(self._lifecycle)
        self._web = Web(self, self._lifecycle, root_dir)

    def all_projects(self):
        return self._repository.all_projects()

    def create_project(self, name):
        self._repository.save_project(Project(name))

    def run(self):
        self._lifecycle.start()
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


class Web:
    def __init__(self, app, lifecycle, root_dir):
        routes = [
            ('/', self.on_index),
            ('/project', self.on_create_project, ['PUT']),
        ]
        statics = {'/static': root_dir / 'static'}

        self._app = app
        self._server = HttpServer(lifecycle, root_dir / 'templates', routes, statics)

    def on_index(self, _request):
        projects = self._app.all_projects()
        return self._server.render('projects', projects=projects)

    def on_create_project(self, request):
        name = request.form['name']
        self._app.create_project(name)
        return self._server.redirect('on_index')

    def run(self):
        self._server.run()

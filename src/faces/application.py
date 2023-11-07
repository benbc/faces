from dataclasses import dataclass

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema

from . import infrastructure

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
        self._database = infrastructure.Database(lifecycle)
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

class Web:
    def __init__(self, lifecycle, template_dir):
        self._faces = Faces(lifecycle)
        self._wz_app = infrastructure.WZApp(
            endpoints=self,
            routes=[
                infrastructure.WZApp.route('/', endpoint='index'),
                infrastructure.WZApp.route('/project', endpoint='create_project', methods=['PUT']),
            ],
            template_dir=template_dir,
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

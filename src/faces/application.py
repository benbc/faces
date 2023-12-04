from dataclasses import dataclass

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.schema

from . import infrastructure

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
        return cls(infrastructure.Database.create(lifecycle), lifecycle)

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

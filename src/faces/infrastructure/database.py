from dataclasses import dataclass

import flask
import sqlalchemy

from faces.domain import Project

@dataclass
class Tables:
    projects = sqlalchemy.Table('projects', sqlalchemy.MetaData(),
                                sqlalchemy.Column('name', sqlalchemy.Text))
tables = Tables()

class Database:
    def execute(self, query, params=None):
        return get_db_connection().execute(query, params)

    def commit(self):
        get_db_connection().commit()

class Projects:
    def __init__(self):
        self._db = Database()

    def all(self):
        result = self._db.execute(sqlalchemy.select(tables.projects.c.name))
        return [Project(row.name) for row in result]

    def save(self, p):
        self._db.execute(sqlalchemy.insert(tables.projects).values(name=p.name))
        self._db.commit()

engine = sqlalchemy.create_engine('sqlite+pysqlite:///file:faces.db', echo=True)

def get_db_connection():
    if 'db_connection' not in flask.g:
        flask.g.db_connection = engine.connect()
    try:
        print('projects:')
        print(list(flask.g.db_connection.execute(sqlalchemy.text("SELECT * from projects"))))
    except Exception as e:
        print(e)
    return flask.g.db_connection

def init_db(flask_app):
    with flask_app.app_context():
        with get_db_connection() as connection:
            connection.execute(sqlalchemy.text("CREATE TABLE projects (name text)"))
            connection.execute(
                sqlalchemy.text("INSERT INTO projects (name) VALUES (:name)"),
                [{"name": "foo"}, {"name": "bar"}],
            )
            connection.commit()

    with flask_app.app_context():
        c = get_db_connection()
        print("***")
        print(list(c.execute(sqlalchemy.text("SELECT * from projects"))))

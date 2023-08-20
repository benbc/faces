from dataclasses import dataclass

import flask
import flask_sqlalchemy
import sqlalchemy

def init_app():
    return flask.Flask(__name__)

def init_db(app_):
    app_.config["SQLALCHEMY_DATABASE_URI"] = "sqlite+pysqlite:///:memory:"
    app_.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"echo": True}
    fsqla = flask_sqlalchemy.SQLAlchemy()
    fsqla.init_app(app_)

    database = Database(fsqla)
    with app_.app_context():
        database.execute(sqlalchemy.text("CREATE TABLE projects (name text)"))
        database.execute(
            sqlalchemy.text("INSERT INTO projects (name) VALUES (:name)"),
            [{"name": "foo"}, {"name": "bar"}],
        )
        database.commit()
        database.load_tables()
    return database

@dataclass
class Tables:
    projects: sqlalchemy.Table

class Database:
    def __init__(self, fsqla):
        self._fsqla = fsqla
        self.tables = None

    def execute(self, query, params=None):
        return self._fsqla.session.execute(query, params)

    def commit(self):
        self._fsqla.session.commit()

    def load_tables(self):
        self.tables = Tables(
            projects=sqlalchemy.Table("projects", self._fsqla.metadata, autoload_with=self._fsqla.engine)
        )

def create_application(app, db):
    @app.route('/')
    def projects():
        ps = Projects(db).all()
        return flask.render_template('projects.jinja', projects=ps)


    @app.route('/project', methods=['PUT'])
    def create_project():
        p = Project.create(flask.request.form['name'])
        Projects().save(p)
        return flask.redirect(flask.url_for('projects'), 303)

class Project:
    @classmethod
    def create(cls, name):
        return cls(name)

    def __init__(self, name):
        self.name = name

class Projects:
    def __init__(self, db):
        self._db = db

    def all(self):
        result = self._db.execute(sqlalchemy.select(self._db.tables.projects.c.name))
        return [Project(row.name) for row in result]

    def save(self, p):
        self._db.execute(sqlalchemy.insert(self._db.tables.projects).values(name=p.name))
        self._db.commit()

app = init_app()
db = init_db(app)
create_application(app, db)

import sqlalchemy

from faces.application import Repository, Project, tables
from faces.infrastructure import Database


def test_returns_all_projects():
    database = Database.create_null([{'name': 'one'}, {'name': 'two'}])
    queries = database.track_queries()

    projects = Repository(database).all_projects()

    assert_queries(queries.last(), sqlalchemy.select(tables.projects.c.name))
    assert projects == [Project('one'), Project('two')]


def test_saves_a_project():
    database = Database.create_null()
    queries = database.track_queries()

    Repository(database).save_project(Project('a'))

    assert_queries(queries.last(), sqlalchemy.insert(tables.projects).values(name='a'))

def assert_queries(left, right):
    left_compiled = left.compile(compile_kwargs={"literal_binds": True})
    right_compiled = right.compile(compile_kwargs={"literal_binds": True})
    assert left.compare(right), f'Queries not equivalent:\n{left_compiled}\n{right_compiled}'

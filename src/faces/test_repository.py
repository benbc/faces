import sqlalchemy

from faces.__main__ import Lifecycle
from faces.application import Repository, Project, tables
from faces.infrastructure import Database


def test_returns_all_projects():
    database = Database.create_null([{'name': 'one'}, {'name': 'two'}])
    queries = database.track_queries()

    projects = Repository(Lifecycle(), database).all_projects()

    assert_queries(queries.data[0], sqlalchemy.select(tables.projects.c.name))
    assert projects == [Project('one'), Project('two')]


def assert_queries(left, right):
    assert left.compare(right), f'Queries not equivalent:\n{left.compile()}\n{right.compile()}'

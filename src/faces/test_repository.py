import sqlalchemy
import sqlalchemy.exc

from .application import Repository, Project, tables
from .infrastructure.http_server import Lifecycle
from .infrastructure.database import Database


def test_returns_all_projects():
    database = Database.create_null([[{'name': 'one'}, {'name': 'two'}]])
    projects = Repository(database).all_projects()

    assert_queries(database.query_tracker.last_output(), sqlalchemy.select(tables.projects.c.name))
    assert projects == [Project('one'), Project('two')]


def test_saves_a_project():
    database = Database.create_null()
    Repository(database).save_project(Project('a'))

    assert_queries(database.query_tracker.last_output(), sqlalchemy.insert(tables.projects).values(name='a'))


def test_checks_whether_project_table_exists_on_startup():
    database = Database.create_null()

    lifecycle = Lifecycle()
    Repository(database, lifecycle)
    lifecycle.start()

    assert_queries(database.query_tracker.last_output(), sqlalchemy.select(tables.projects.c.name))


def test_ensures_that_project_table_exists_on_startup():
    database = Database.create_null([sqlalchemy.exc.OperationalError(None, None, None), [], []])
    lifecycle = Lifecycle()
    Repository(database, lifecycle)
    lifecycle.start()

    assert_queries(database.query_tracker.last_batch(), [
        sqlalchemy.select(tables.projects.c.name),
        sqlalchemy.schema.CreateTable(tables.projects),
        sqlalchemy.insert(tables.projects).values([{'name': 'foo'}, {'name': 'bar'}])
    ])


def assert_queries(lefts, rights):
    try:
        for left, right in zip(lefts, rights):
            assert_one_query(left, right)
        assert len(lefts) == len(rights), f"Expected {len(rights)} queries, but got {len(lefts)}"
    except TypeError:
        assert_one_query(lefts, rights)


def assert_one_query(left, right):
    left_compiled = compile(left)
    right_compiled = compile(right)
    assert left_compiled == right_compiled, f'Queries not equivalent:\n{left_compiled}\n{right_compiled}'


def compile(query):
    return str(query.compile(compile_kwargs={"literal_binds": True}))

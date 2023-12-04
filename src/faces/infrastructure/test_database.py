import threading

import sqlalchemy
from sqlalchemy import Text, Table, MetaData, Column

from .web import Lifecycle
from .database import Database

def make_table(db, column):
    table = Table('the_table', MetaData(), Column(column, Text))
    db.execute(sqlalchemy.schema.CreateTable(table))
    db.commit()
    return table

def test_executes_queries():
    db = Database('sqlite:///:memory:')
    table = make_table(db, 'foo')
    db.execute(sqlalchemy.insert(table).values(foo='bar'))
    rows = list(db.execute(sqlalchemy.select(table.c.foo)))
    assert rows == [('bar',)]

def test_rollback_rolls_back():
    db = Database('sqlite:///:memory:')
    table = make_table(db, 'foo')
    rows = list(db.execute(sqlalchemy.select(table.c.foo)))
    assert not rows

    # Within the same transaction we can see the result of an insertion
    db.execute(sqlalchemy.insert(table).values(foo='bar'))
    rows = list(db.execute(sqlalchemy.select(table.c.foo)))
    assert rows

    # But after rollback the new row has disappeared
    db.rollback()
    rows = list(db.execute(sqlalchemy.select(table.c.foo)))
    assert not rows

def test_isolates_queries_in_transactions(tmp_path):
    uri = f'sqlite+pysqlite:///{tmp_path / "test.db"}'
    db1 = Database(uri)
    table = make_table(db1, 'foo')

    # Insert a row without committing
    db1.execute(sqlalchemy.insert(table).values(foo='bar'))

    # With a separate connection we can't see the inserted row
    db2 = Database(uri)
    rows = list(db2.execute(sqlalchemy.select(table.c.foo)))
    assert not rows

    # After committing the inserted row becomes visible to the other connection
    db1.commit()
    rows = list(db2.execute(sqlalchemy.select(table.c.foo)))
    assert rows

def test_provides_per_thread_transactions(tmp_path, reraise):
    uri = f'sqlite+pysqlite:///{tmp_path / "test.db"}'
    db = Database(uri)
    table = make_table(db, 'foo')

    commit_barrier = threading.Barrier(parties=2, timeout=1)

    # Insert a row without committing
    db.execute(sqlalchemy.insert(table).values(foo='bar'))

    # On a separate thread we can't see the inserted row
    def check():
        rows = list(db.execute(sqlalchemy.select(table.c.foo)))
        with reraise:
            assert not rows

        commit_barrier.wait()  # signal ready for commit
        commit_barrier.wait()  # commit has happened

        rows = list(db.execute(sqlalchemy.select(table.c.foo)))
        with reraise:
            assert rows

    threading.Thread(target=check).start()

    commit_barrier.wait()  # thread is ready
    db.commit()
    commit_barrier.wait()  # signal commit has happened

def test_request_success_triggers_commit(tmp_path):
    uri = f'sqlite+pysqlite:///{tmp_path / "test.db"}'
    lifecycle = Lifecycle()
    db1 = Database(uri, lifecycle)
    table = make_table(db1, 'foo')

    # Write a row on one connection
    db1.execute(sqlalchemy.insert(table).values(foo='bar'))

    # Trigger a commit
    lifecycle.request_success()

    # The row is visible to another connection
    db2 = Database(uri)
    rows = list(db2.execute(sqlalchemy.select(table.c.foo)))
    assert rows

def test_request_failure_triggers_rollback():
    lifecycle = Lifecycle()
    db = Database('sqlite:///:memory:', lifecycle)
    table = make_table(db, 'foo')

    # Write a row
    db.execute(sqlalchemy.insert(table).values(foo='bar'))

    # Trigger a rollback
    lifecycle.request_failure()

    # The row has vanished
    rows = list(db.execute(sqlalchemy.select(table.c.foo)))
    assert not rows

from collections import namedtuple
from contextvars import ContextVar

import sqlalchemy

from .support import OutputTracker


class Database:
    def __init__(self, uri, lifecycle=None, engine=sqlalchemy.create_engine):
        self._engine = engine(uri, echo=True)
        self._context_var = ContextVar('connection')

        if lifecycle:
            lifecycle.add_request_listener(success=self.commit, failure=self.rollback)

        self.query_tracker = OutputTracker()

    @classmethod
    def create(cls, lifecycle):
        return cls('sqlite+pysqlite:///faces.db', lifecycle)

    @classmethod
    def create_null(cls, responses=None):
        if not responses:
            responses = [[]]
        return cls('', engine=_StubEngine(responses))

    def execute(self, statement, parameters=None):
        self.query_tracker.add(statement)
        return self._connection().execute(statement, parameters)

    def commit(self):
        self._finalize_connection(lambda c: c.commit())

    def rollback(self):
        self._finalize_connection(lambda c: c.rollback())

    def _finalize_connection(self, operation):
        c = self._maybe_connection()
        if not c:
            return
        operation(c)
        c.close()
        self._context_var.set(None)
        self.query_tracker.end_batch()

    def _connection(self):
        c = self._maybe_connection()
        if not c:
            c = self._engine.connect()
            self._context_var.set(c)
        return c

    def _maybe_connection(self):
        return self._context_var.get(None)


class _StubEngine:
    def __init__(self, responses):
        self._responses = responses

    def __call__(self, _uri, **kwargs):
        return self

    def connect(self):
        return _StubConnection(self._responses)


class _StubConnection:
    def __init__(self, responses):
        self._responses = responses

    def execute(self, statement, parameters):
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if response:
            Record = namedtuple('Record', response[0])
            return [Record(**row) for row in response]
        return []

    def commit(self):
        pass

    def close(self):
        pass

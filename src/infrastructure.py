from contextvars import ContextVar

import sqlalchemy

class Database:
    def __init__(self, lifecycle):
        self._engine = sqlalchemy.create_engine('sqlite+pysqlite:///faces.db', echo=True)
        self._context_var = ContextVar('connection')

        lifecycle.add_request_listener(success=self.commit, failure=self.rollback)

    def execute(self, statement, parameters=None):
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

    def _connection(self):
        c = self._maybe_connection()
        if not c:
            c = self._engine.connect()
            self._context_var.set(c)
        return c

    def _maybe_connection(self):
        return self._context_var.get(None)

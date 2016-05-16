from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import DatabaseError
from smslogger import settings, queries


class PoolManager(object):
    def __init__(self):
        self.pool = self._new_pool()

    @staticmethod
    def _new_pool():
        return ThreadedConnectionPool(minconn=2, maxconn=5, **settings.POSTGRES)

    @contextmanager
    def db_cursor(self):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(queries.CHECK_CONNECTION)
        except DatabaseError:
            self.pool.closeall()
            self.pool = self._new_pool()
            conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur
                conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def close_pool(self):
        self.pool.closeall()

pool = PoolManager()


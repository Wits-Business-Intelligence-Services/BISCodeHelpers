import sqlalchemy as __sq__
from logging import Logger as __Logger__
from helpers.logged_exceptions import LoggedDatabaseError as __LoggedDatabaseError__


# ----------------------------------------------------
# Function for creating and testing an Oracle DB engine
# ----------------------------------------------------


def create_engine(username: str, password: str, database: str, logger: __Logger__):
    """
    Sets up a database connection engine used to execute queries.

    :param username: (str): Username for DB
    :param password: (str): Password for DB
    :param database: (str): DB address
    :param logger: (logging.Logger): Logger for logging debug and error messages.
    :return: (sqlalchemy.engine): Database connection engine.
    """
    conn_string: str = "oracle+cx_oracle://" + username + ":" + password + "@" + database
    # print(conn_string)
    engine = __sq__.create_engine(conn_string, pool_size=30, max_overflow=-1)

    try:
        with ConnectionManager(engine):
            logger.debug(
                "Got DB Connection: " + database
            )
    except Exception as e:
        raise __LoggedDatabaseError__(
            logger,
            "failed to connect to DB: {DB}\n{error}".format(
                DB=database, error=str(e)
            ),
        )

    return engine


# ----------------------------------------------------
# Context manager class to open and close connections as required
# ----------------------------------------------------


class ConnectionManager:
    """
    Context manager class to open and close connections as required.
    """

    def __init__(self, engine: __sq__.engine):
        self.engine: __sq__.engine = engine

    def __enter__(self):
        self.connection: __sq__.engine.base.Connection = self.engine.connect()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()
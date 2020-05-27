import pandas as __pd__
import helpers
from typing import Optional as __Optional__
import sqlalchemy as __sq__
from logging import Logger as __Logger__
import time as __time__


def get_db_table_column_names(
    table_name: str, engine: __sq__.engine
) -> __Optional__[list]:
    """
    Get column names of table on database.

    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :return: (Optional[list]): List of column names, None if table does not exist.
    """
    query: str = helpers.utils.generate_column_names_of_db_table_query(table_name)
    with helpers.ConnectionManager(engine) as conn:
        try:
            result = __pd__.read_sql(query, conn)
            col_names = list(result.columns)
            return col_names
        except __sq__.exc.DatabaseError as error:
            if "table or view does not exist" in str(error):
                return None


def get_db_table_row_count(table_name: str, engine: __sq__.engine) -> __Optional__[int]:
    """
    Get row count of table on database.

    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :return: Number of rows, None if table does not exist.
    """
    query: str = helpers.utils.generate_get_number_of_rows_of_db_table_query(table_name)
    with helpers.ConnectionManager(engine) as conn:
        try:
            result = __pd__.read_sql(query, conn)
            count: int = result["COUNT(*)"].iloc[0]
            return count
        except __sq__.exc.DatabaseError as error:
            if "table or view does not exist" in str(error):
                return None


def truncate_table(
    table_name: str, engine: __sq__.engine, logger: __Logger__ = None
) -> None:
    """
    Truncate staging or prod table.

    :param logger: (logging.logger): Logger to use for logging
    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :return: None
    """

    if logger is None:
        logger = helpers.utils.MockLogger()

    query: str = helpers.utils.generate_trunc_db_table_query(table_name)

    with helpers.ConnectionManager(engine) as conn:
        trans = conn.begin()
        try:
            conn.execute(query)
            logger.info(
                "Truncated table {table_name} on DB.".format(table_name=table_name)
            )
        except Exception as e:
            if "table or view does not exist" in str(e):
                pass
            else:
                raise helpers.LoggedDatabaseError(logger, str(e))

        trans.commit()


def drop_table(
    table_name: str, engine: __sq__.engine, logger: __Logger__ = None
) -> None:
    """
    Drop staging or prod table.

    :param logger: (logging.logger): Logger to use for logging
    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :param staging: (bool): If True, drop staging table, else prod table will be dropped.
    :return: None
    """

    if logger is None:
        logger = helpers.utils.MockLogger()

    query: str = helpers.utils.generate_drop_db_table_query(table_name)

    with helpers.ConnectionManager(engine) as conn:
        trans = conn.begin()
        try:
            conn.execute(query)
            logger.info(
                "Dropped table {table_name} on DB.".format(table_name=table_name)
            )
        except Exception as e:
            if "table or view does not exist" in str(e):
                pass
            else:
                raise helpers.LoggedDatabaseError(logger, str(e))

        trans.commit()


def create_table(
    data_results: __pd__.DataFrame,
    table_name: str,
    engine: __sq__.engine,
    allow_nulls: bool = True,
    use_date_created: bool = False,
    logger: __Logger__ = None,
) -> None:
    """
    Create table. If table already exists, check to see that the column names
    match for compatibility.
    :param allow_nulls: (bool): Allow nulls in table.
    :param use_date_created: (bool): Include a 'DATE_CREATED' column with current date and time.
    :param logger: (logging.logger): Logger to use for logging
    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :param data_results: (pd.DataFrame): Data to use for generating column names and data types.
    :param staging: (bool): If True, create staging table, else prod table will be created.
    :return: None
    """

    if logger is None:
        logger = helpers.utils.MockLogger()

    # Check if table already exists
    db_col_names: __Optional__[list] = get_db_table_column_names(table_name, engine)
    # If the table does not exist
    if not db_col_names:
        # Formulate and execute query to create table on DB
        create_query: str = helpers.utils.generate_table_creation_query(
            data_results,
            table_name,
            allow_nulls,
            use_date_created,
        )

        with helpers.ConnectionManager(engine) as conn:
            trans = conn.begin()

            try:
                conn.execute(create_query)
                logger.info(
                    "Created table {table_name} on DB.".format(table_name=table_name)
                )
            except Exception as e:
                if "name is already used by an existing object" in str(e):
                    logger.info(
                        "Table {table_name} already exists on DB.".format(
                            table_name=table_name
                        )
                    )
                else:
                    raise helpers.LoggedDatabaseError(logger, str(e))

            trans.commit()
    else:
        # Formatting
        db_col_names: list = [x.upper() for x in db_col_names]
        new_data_col_names: list = [
            x.upper().replace(" ", "_") for x in list(data_results.columns)
        ]

        # Add DATE_CREATED since it is added later
        if use_date_created:
            new_data_col_names.append("DATE_CREATED")

        # Convert to sets for comparison operations
        db_col_names_set: set = set(db_col_names)
        new_data_col_names_set: set = set(new_data_col_names)

        # Check for differences
        if db_col_names_set != new_data_col_names_set:
            union: set = db_col_names_set.union(new_data_col_names_set)
            diff: set = (union - new_data_col_names_set).union(union - db_col_names_set)
            raise helpers.LoggedDataError(
                logger,
                "data columns do not match database columns: {diff} for table {table_name}".format(
                    diff=diff, table_name=table_name
                ),
            )


def upload_data_to_table(
    table_data: __pd__.DataFrame,
    upload_partition_size: int,
    table_name: str,
    engine: __sq__.engine,
    use_date_created: bool = False,
    logger: __Logger__ = None,
) -> None:
    """
    Upload data in table_data DataFrame to table.

    :param use_date_created: (bool): Include a 'DATE_CREATED' column with current date and time.
    :param logger: (logging.logger): Logger to use for logging
    :param engine: (sqlalchemy.engine) DB engine used for DB connection.
    :param table_name: (str): Name of table to perform operation on.
    :param upload_partition_size:
    :param table_data: (pd.DataFrame): data to be uploaded.
    :return: None
    """

    if logger is None:
        logger = helpers.utils.MockLogger()

    iterator_index: int = 0
    data_num_records: int = len(table_data.index)

    date_created = __time__.strftime("%d/%b/%y %H:%M:%S").upper()
    date_str: str = "to_date('{date_created}','dd/mon/yy hh24:mi:ss')".format(
        date_created=date_created
    )
    if use_date_created:
        table_data["DATE_CREATED"] = date_str
    with helpers.ConnectionManager(engine) as conn:
        while (iterator_index + 1) * upload_partition_size < data_num_records:
            print(
                "Uploading rows: {a} - {b}".format(
                    a=str(iterator_index * upload_partition_size),
                    b=str((iterator_index + 1) * upload_partition_size - 1),
                )
            )
            insert_query: str = helpers.utils.generate_insert_query(
                table_data[
                    iterator_index
                    * upload_partition_size : (iterator_index + 1)
                    * upload_partition_size
                ],
                table_name,
            )

            trans = conn.begin()
            conn.execute(insert_query)
            trans.commit()
            iterator_index += 1

        print(
            "Uploading rows: {a} - {b}".format(
                a=str(iterator_index * upload_partition_size), b=str(data_num_records),
            )
        )
        # Final non divisible rows
        insert_query: str = helpers.utils.generate_insert_query(
            table_data[iterator_index * upload_partition_size :], table_name,
        )

        trans = conn.begin()
        conn.execute(insert_query)
        trans.commit()
    logger.info("Completed upload of data to table.")
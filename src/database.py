from datetime import datetime
from typing import Any, Tuple, List

import psycopg2

from config import Config
from structs import Break


def connect(config: Config) -> Tuple[Any, Any]:
    conn = psycopg2.connect(
        dbname=config.db.database,
        user=config.db.user,
        password=config.db.password,
        host=config.db.host
    )
    cur = conn.cursor()
    return (conn, cur)


def disconnect(conn: Any, cur: Any) -> None:
    conn.close()
    cur.close()


def insert_host(config: Config, break_host: str, break_id: int) -> None:
    (conn, cur) = connect(config)
    statement = """
        UPDATE cookiebreak
        SET break_host = %s
        WHERE break_id = %s
    """
    cur.execute(statement, (break_host, break_id))
    conn.commit()
    disconnect(conn, cur)


def get_next_breaks(config: Config, number: int) -> List[Break]:
    today = datetime.now()
    (conn, cur) = connect(config)
    statement = f"""
        SELECT break_id, break_host, break_datetime, break_location, is_holiday
        FROM cookiebreak
        WHERE break_datetime > %s
        ORDER BY break_datetime ASC
    """
    cur.execute(statement, (today,))
    rows = cur.fetchmany(size=number)
    disconnect(conn, cur)
    next_breaks = []
    for row in rows:
        (id, break_host, date, break_location, holiday) = row
        next_breaks.append(
            Break(id, break_host, date, break_location, holiday))
    return next_breaks


def get_next_break(config: Config) -> Break:
    return get_next_breaks(config, 1)[0]


def insert_missing_breaks(config: Config, breaks: List[Break]) -> None:
    (conn, cur) = connect(config)
    for b in breaks:
        statement = """
            INSERT INTO cookiebreak (break_datetime, break_location)
            VALUES (%s, %s)
        """
        try:
            cur.execute(
                statement,
                (b.time, b.location)
            )
        except Exception as e:
            print(e)
            # If the break already exists then the above query throws an error
            # Postgres >= 9.5 has an ON CONFLICT keyword that lets us do this
            # natively but the version on the CS server is only 9.2 so we can't
            # do that and we hack it instead
            conn.rollback()
    conn.commit()
    disconnect(conn, cur)


def set_holiday(config: Config, break_id: int, holiday: bool) -> None:
    (conn, cur) = connect(config)
    if holiday:
        statement = """
            UPDATE cookiebreak
            SET is_holiday = true, break_host = NULL
            WHERE break_id = %s
        """
    else:
        statement = """
            UPDATE cookiebreak
            SET is_holiday = false
            WHERE break_id = %s
        """
    cur.execute(statement, (break_id, ))
    conn.commit()
    disconnect(conn, cur)

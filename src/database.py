from datetime import datetime
from typing import Any

import psycopg2

from config import Config
from structs import Break


def connect(config: Config) -> tuple[Any, Any]:
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


def get_next_breaks(config: Config, number: int) -> list[Break]:
    today = datetime.now()
    (conn, cur) = connect(config)
    statement = f"""
        SELECT break_id, host, break_date, location
        FROM cookiebreak
        WHERE break_date > %s
        ORDER BY break_date ASC
    """
    cur.execute(statement, (today,))
    rows = cur.fetchmany(size=number)
    disconnect(conn, cur)
    next_breaks = []
    for row in rows:
        (id, host, date, location) = row
        next_breaks.append(Break(id, host, date, location))
    return next_breaks


def get_next_break(config: Config) -> Break:
    return get_next_breaks(config, 1)[0]


def insert_host(config: Config, host: str, break_id: int) -> None:
    (conn, cur) = connect(config)
    statement = f"""
        UPDATE cookiebreak
        SET host = '%s'
        WHERE break_id = '%n'
    """
    cur.execute(statement, host, break_id)
    disconnect(conn, cur)

import os
import logging
import psycopg2
from psycopg2 import pool
from fastapi import HTTPException, status
import clickhouse_connect
from security import hash_password

logger = logging.getLogger("DashboardBackend.Database")

_db_pool = None

def init_pool():
    global _db_pool
    if _db_pool is not None:
        return
    host = os.getenv("POSTGRES_HOST", "postgres").strip().strip("'\"")
    port = int(os.getenv("POSTGRES_PORT", 5432))
    user = os.getenv("POSTGRES_USER", "postgres").strip().strip("'\"")
    password = os.getenv("POSTGRES_PASSWORD", "postgres").strip().strip("'\"")
    dbname = os.getenv("POSTGRES_DB", "iiot_db").strip().strip("'\"")

    try:
        _db_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=30,
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        logger.info("PostgreSQL ThreadedConnectionPool initialized.")
    except Exception as e:
        if host not in ("127.0.0.1", "localhost"):
            logger.info(f"Failed to connect pool at '{host}'. Trying fallback to '127.0.0.1'...")
            try:
                _db_pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=30,
                    host="127.0.0.1",
                    port=port,
                    user=user,
                    password=password,
                    dbname=dbname
                )
                logger.info("PostgreSQL Fallback ThreadedConnectionPool initialized.")
                return
            except Exception as inner_e:
                logger.error(f"Fallback connection pool to 127.0.0.1 also failed: {inner_e}")
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        raise e

def get_db_connection():
    global _db_pool
    if _db_pool is None:
        init_pool()
    try:
        return _db_pool.getconn()
    except Exception as e:
        logger.error(f"Error getting connection from pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database pool error: {e}"
        )

def release_db_connection(conn):
    global _db_pool
    if _db_pool is not None and conn is not None:
        _db_pool.putconn(conn)


class PostgresResult:
    def __init__(self, result_rows, column_names):
        self.result_rows = result_rows
        self.column_names = column_names

class PostgresClient:
    def __init__(self, conn):
        self.conn = conn

    def query(self, sql, parameters=None):
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, parameters)
                try:
                    rows = cur.fetchall()
                    col_names = [desc[0] for desc in cur.description] if cur.description else []
                    return PostgresResult(rows, col_names)
                except psycopg2.ProgrammingError:
                    return PostgresResult([], [])
        except Exception as e:
            self.conn.rollback()
            raise e

    def insert(self, table, data, column_names=None):
        try:
            cols = ", ".join([f'"{c}"' for c in column_names])
            placeholders = ", ".join(["%s"] * len(column_names))
            sql = f'INSERT INTO {table} ({cols}) VALUES ({placeholders})'
            with self.conn.cursor() as cur:
                for row in data:
                    cur.execute(sql, row)
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def command(self, sql, parameters=None):
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, parameters)
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

def get_ch_client():
    """
    Dependency helper that returns a PostgresClient wrapper.
    Named get_ch_client to maintain backward compatibility with routers/ dependencies.
    """
    conn = get_db_connection()
    try:
        yield PostgresClient(conn)
    finally:
        release_db_connection(conn)

_ch_client = None

def get_clickhouse_client():
    global _ch_client
    if _ch_client is not None:
        return _ch_client

    host = os.getenv("CLICKHOUSE_HOST", "clickhouse").strip().strip("'\"")
    port = int(os.getenv("CLICKHOUSE_PORT", 8123))
    user = os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\"")
    password = os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\"")
    database = os.getenv("CLICKHOUSE_DATABASE", "default").strip().strip("'\"")
    try:
        _ch_client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database
        )
        return _ch_client
    except Exception as e:
        if host not in ("127.0.0.1", "localhost"):
            logger.info(f"Failed to connect to ClickHouse at '{host}'. Trying fallback to '127.0.0.1'...")
            try:
                _ch_client = clickhouse_connect.get_client(
                    host="127.0.0.1",
                    port=port,
                    username=user,
                    password=password,
                    database=database
                )
                return _ch_client
            except Exception as inner_e:
                logger.error(f"Fallback connection to 127.0.0.1 also failed: {inner_e}")
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {e}"
        )

def format_result(result):
    if not result or not hasattr(result, 'result_rows'):
        return []
    return [dict(zip(result.column_names, row)) for row in result.result_rows]

def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Create tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    "user" VARCHAR(255) PRIMARY KEY,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'user'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS device_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    process VARCHAR(255) NOT NULL,
                    device VARCHAR(255) NOT NULL,
                    PRIMARY KEY (process, device)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS columns_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    process VARCHAR(255) NOT NULL,
                    column_name VARCHAR(255) NOT NULL,
                    column_type VARCHAR(50) NOT NULL,
                    column_key BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (process, column_name)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS project_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    items VARCHAR(255) PRIMARY KEY,
                    value VARCHAR(255) NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS status_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    process VARCHAR(255) NOT NULL,
                    status VARCHAR(255) NOT NULL,
                    color VARCHAR(50) NOT NULL,
                    PRIMARY KEY (process, status)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alarm_register_tb (
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    process VARCHAR(255) NOT NULL,
                    status VARCHAR(255) NOT NULL,
                    color VARCHAR(50) NOT NULL,
                    PRIMARY KEY (process, status)
                );
            """)

            # 2. Insert default users if empty
            cur.execute("SELECT COUNT(*) FROM user_register_tb;")
            if cur.fetchone()[0] == 0:
                logger.info("Initializing default users in user_register_tb...")
                cur.execute("""
                    INSERT INTO user_register_tb ("user", password, role)
                    VALUES (%s, %s, 'admin'), (%s, %s, 'user');
                """, ("admin", hash_password("admin"), "user", hash_password("user")))

            # 3. Insert default project configurations if empty
            cur.execute("SELECT COUNT(*) FROM project_register_tb;")
            if cur.fetchone()[0] == 0:
                logger.info("Initializing default settings in project_register_tb...")
                cur.execute("""
                    INSERT INTO project_register_tb (items, value)
                    VALUES 
                        ('division', 'mic'),
                        ('server_IP', '0.0.0.0'),
                        ('record_period', '60');
                """)

            # # 4. Insert default columns if empty
            # cur.execute("SELECT COUNT(*) FROM columns_register_tb;")
            # if cur.fetchone()[0] == 0:
            #     logger.info("Initializing default columns in columns_register_tb...")
            #     cur.execute("""
            #         INSERT INTO columns_register_tb (process, column_name, column_type, column_key)
            #         VALUES 
            #             ('demo1', 'model', 'String', TRUE),
            #             ('demo1', 'data1', 'Float32', FALSE),
            #             ('demo1', 'data2', 'Float32', FALSE),
            #             ('demo1', 'data3', 'Float32', FALSE),
            #             ('demo1', 'data4', 'Float32', FALSE),
            #             ('demo1', 'data5', 'Float32', FALSE),
            #             ('demo1', 'data6', 'Float32', FALSE),
            #             ('demo1', 'data7', 'Float32', FALSE);   
            #     """)

            # 5. Insert default devices if empty
            # cur.execute("SELECT COUNT(*) FROM device_register_tb;")
            # if cur.fetchone()[0] == 0:
            #     logger.info("Initializing default devices in device_register_tb...")
            #     for i in range(1, 1001):
            #         cur.execute("""
            #             INSERT INTO device_register_tb (process, device)
            #             VALUES ('demo1', %s) ON CONFLICT DO NOTHING;
            #         """, (f"no_{i}",))

            conn.commit()
            logger.info("PostgreSQL database tables initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during database initialization: {e}")
        raise e
    finally:
        release_db_connection(conn)


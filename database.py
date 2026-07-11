"""
Database Connection and CRUD operations using mysql-connector-python.
Implements a Connection Pool for optimal performance.
"""

import mysql.connector
from mysql.connector import pooling
from mysql.connector import Error
from config import Config
from utils import logger

class Database:
    """Handles MySQL Database connections and execution."""
    _pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the database connection pool."""
        if cls._pool is None:
            try:
                cls._pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="retailiq_pool",
                    pool_size=5,
                    pool_reset_session=True,
                    host=Config.DB_HOST,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME
                )
                logger.info("Database connection pool initialized successfully.")
            except Error as e:
                logger.error(f"Error initializing connection pool: {e}")
                # Fallback or allow app to start but flag DB as offline

    @classmethod
    def get_connection(cls):
        """Gets a connection from the pool."""
        if cls._pool is None:
            cls.initialize_pool()
        try:
            return cls._pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None

    @classmethod
    def execute_query(cls, query, params=None, fetch=False, fetch_all=True):
        """
        Executes an SQL query.
        :param query: SQL string
        :param params: Tuple of parameters
        :param fetch: Boolean indicating if results should be fetched
        :param fetch_all: Boolean indicating if fetchall() (True) or fetchone() (False) should be used
        :return: Fetched data or row count
        """
        conn = cls.get_connection()
        if conn is None:
            return None

        cursor = conn.cursor(dictionary=True) # Return results as dictionaries
        result = None
        try:
            cursor.execute(query, params or ())
            
            if fetch:
                if fetch_all:
                    result = cursor.fetchall()
                else:
                    result = cursor.fetchone()
            else:
                conn.commit()
                result = cursor.rowcount
                
        except Error as e:
            logger.error(f"Database Query Error: {e}")
            if not fetch:
                conn.rollback()
        finally:
            cursor.close()
            if conn.is_connected():
                conn.close() # Returns connection to pool
            
        return result

    @classmethod
    def insert_many(cls, query, params_list):
        """
        Executes an executemany for bulk inserts.
        """
        conn = cls.get_connection()
        if conn is None:
            return False

        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Error as e:
            logger.error(f"Database Bulk Insert Error: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            if conn.is_connected():
                conn.close()

"""
Database Module for Credit Risk Monitoring System
Handles database connections, schema initialization, and basic operations.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import DatabaseConfig, BASE_DIR


class DatabaseManager:
    """
    Manages SQLite database connections and operations for the
    Credit Risk Monitoring System.
    """

    def __init__(self, db_path: Optional[Path] = None, mode: str = 'demo'):
        """
        Initialize database manager.

        Args:
            db_path: Optional custom database path
            mode: 'demo' for demo database, 'real' for production database
        """
        if db_path:
            self.db_path = Path(db_path)
        elif mode == 'real':
            self.db_path = DatabaseConfig.REAL_DB_PATH
        else:
            self.db_path = DatabaseConfig.DEMO_DB_PATH

        self.schema_path = DatabaseConfig.SCHEMA_PATH
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all necessary directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures proper connection handling and cleanup.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_pandas_connection(self):
        """Get a connection suitable for pandas operations."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize_database(self, force_recreate: bool = False):
        """
        Initialize database with schema.

        Args:
            force_recreate: If True, drop and recreate all tables
        """
        if force_recreate and self.db_path.exists():
            self.db_path.unlink()

        with open(self.schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            print(f"Database initialized at: {self.db_path}")

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """
        Execute a SELECT query and return results as list of dicts.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries with query results
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def execute_dataframe(self, query: str, params: tuple = ()) -> pd.DataFrame:
        """
        Execute a SELECT query and return results as pandas DataFrame.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            pandas DataFrame with query results
        """
        conn = self.get_pandas_connection()
        try:
            df = pd.read_sql_query(query, conn, params=params)
            return df
        finally:
            conn.close()

    def execute_insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert a single row into a table.

        Args:
            table: Table name
            data: Dictionary of column names and values

        Returns:
            ID of inserted row
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.execute(query, tuple(data.values()))
            return cursor.lastrowid

    def execute_insert_many(self, table: str, data: List[Dict[str, Any]]) -> int:
        """
        Insert multiple rows into a table.

        Args:
            table: Table name
            data: List of dictionaries with column names and values

        Returns:
            Number of inserted rows
        """
        if not data:
            return 0

        columns = ', '.join(data[0].keys())
        placeholders = ', '.join(['?' for _ in data[0]])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.executemany(query, [tuple(d.values()) for d in data])
            return cursor.rowcount

    def execute_update(self, table: str, data: Dict[str, Any],
                       where: str, where_params: tuple) -> int:
        """
        Update rows in a table.

        Args:
            table: Table name
            data: Dictionary of column names and new values
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of updated rows
        """
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"

        with self.get_connection() as conn:
            cursor = conn.execute(query, tuple(data.values()) + where_params)
            return cursor.rowcount

    def execute_delete(self, table: str, where: str, where_params: tuple) -> int:
        """
        Delete rows from a table.

        Args:
            table: Table name
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of deleted rows
        """
        query = f"DELETE FROM {table} WHERE {where}"

        with self.get_connection() as conn:
            cursor = conn.execute(query, where_params)
            return cursor.rowcount

    def bulk_insert_dataframe(self, df: pd.DataFrame, table: str,
                               if_exists: str = 'append') -> int:
        """
        Insert a pandas DataFrame into a table.

        Args:
            df: pandas DataFrame
            table: Table name
            if_exists: 'append', 'replace', or 'fail'

        Returns:
            Number of inserted rows
        """
        conn = self.get_pandas_connection()
        try:
            rows = df.to_sql(table, conn, if_exists=if_exists, index=False)
            conn.commit()
            return rows if rows else len(df)
        finally:
            conn.close()

    def get_table_info(self, table: str) -> List[Dict]:
        """Get schema information for a table."""
        return self.execute_query(f"PRAGMA table_info({table})")

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database."""
        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row['name'] for row in result]

    def get_row_count(self, table: str) -> int:
        """Get number of rows in a table."""
        result = self.execute_query(f"SELECT COUNT(*) as count FROM {table}")
        return result[0]['count'] if result else 0

    def backup_database(self, backup_path: Path):
        """
        Create a backup of the database.

        Args:
            backup_path: Path for the backup file
        """
        import shutil
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.db_path, backup_path)
        print(f"Database backed up to: {backup_path}")


# Convenience functions for quick access
def get_demo_db() -> DatabaseManager:
    """Get database manager for demo database."""
    return DatabaseManager(mode='demo')


def get_real_db() -> DatabaseManager:
    """Get database manager for production database."""
    return DatabaseManager(mode='real')


def init_demo_database(force_recreate: bool = True) -> DatabaseManager:
    """Initialize and return demo database."""
    db = get_demo_db()
    db.initialize_database(force_recreate=force_recreate)
    return db


def init_real_database(force_recreate: bool = False) -> DatabaseManager:
    """Initialize and return production database."""
    db = get_real_db()
    db.initialize_database(force_recreate=force_recreate)
    return db


if __name__ == "__main__":
    # Test database initialization
    print("Initializing demo database...")
    db = init_demo_database(force_recreate=True)

    print("\nDatabase tables:")
    for table in db.get_all_tables():
        print(f"  - {table}")

    print("\nDatabase ready for use!")

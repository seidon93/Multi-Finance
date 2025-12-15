import pyodbc
from config.settings import DB_SETTINGS  #  import z konfiguračního souboru


class Database:
    """Třída pro správu připojení a interakci se SQL Serverem."""

    def __init__(self):
        # Nastavení připojovacího řetězce
        self.conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_SETTINGS['SERVER']};"
            f"DATABASE={DB_SETTINGS['DATABASE']};"
            f"TrustServerCertificate=yes;"
            f"Trusted_Connection=yes;"
        )
        self._conn = None

    def __enter__(self):
        """Metoda pro připojení k DB  s 'with' statement"""
        try:
            self._conn = pyodbc.connect(self.conn_str)
            return self._conn
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            print(f"Chyba připojení k databázi: {sqlstate}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Metoda pro uzavření připojení."""
        if self._conn:
            self._conn.close()


def execute_query(sql_query, params=None):
    try:
        with Database() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query, params or ())

            if sql_query.strip().upper().startswith('SELECT'):
                # Pro SELECT dotazy chceme vrátit data
                results = cursor.fetchall()
            else:
                conn.commit()
                results = None

            cursor.close()

            return results

    except Exception as e:
        print(f"Chyba při provádění dotazu: {e}")
        return []


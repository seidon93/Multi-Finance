import os
from core.database import Database


def initialize_database():
    """Načte SQL DDL skript a provede jej pro vytvoření tabulek."""

    # Cesta k SQL souboru
    script_path = os.path.join(os.path.dirname(__file__), '001_initial_sql_schema.sql')

    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        print("Provádím inicializaci databázového schématu...")

        with Database() as conn:
            cursor = conn.cursor()

            # SQL Server může vyžadovat, abychom příkazy spustili po jednom
            # Zde se DDL skript jednoduše provede
            cursor.execute(sql_script)

            conn.commit()
            print("Databázové schéma úspěšně inicializováno.")

    except Exception as e:
        print(f"FATÁLNÍ CHYBA při inicializaci DB: {e}")
        print("Zkontrolujte, zda je SQL Server spuštěn a konfigurační údaje správné.")
        raise


if __name__ == '__main__':
    # Tuto funkci spustíte jednou, abyste vytvořili schéma.
    initialize_database()
# soubor: core/models.py

from core.database import Database


class Transakce:
    """Model pro hlavičku účetní transakce."""

    # Konstruktor odpovídající struktuře tabulky Transakce
    def __init__(self, klient_id, datum, popis, doklad_cislo, id=None):
        self.id = id
        self.klient_id = klient_id
        self.datum = datum
        self.popis = popis
        self.doklad_cislo = doklad_cislo
        self.pohyby = []  # Seznam objektů UcetniPohyb

    def pridat_pohyb(self, ucet, smer, castka):
        """Přidá pohyb k transakci (ale neukládá ho do DB!)."""
        pohyb = UcetniPohyb(self.klient_id, self.id, ucet, smer, castka)
        self.pohyby.append(pohyb)

    def validovat_podvojnost(self):
        """Zkontroluje, zda MD = D v rámci transakce."""
        md_suma = sum(p.castka for p in self.pohyby if p.smer == 'MD')
        d_suma = sum(p.castka for p in self.pohyby if p.smer == 'D')
        return md_suma == d_suma

    def ulozit_transakci(self):
        """Uloží transakci a všechny její pohyby do DB pomocí transakce."""
        if not self.validovat_podvojnost():
            raise ValueError("Chyba: Součet MD se nerovná součtu D.")

        sql_transakce_insert = (
            "INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo) "
            "OUTPUT INSERTED.id "  # Získání nového ID transakce
            "VALUES (?, ?, ?, ?)"
        )

        with Database() as conn:
            cursor = conn.cursor()

            # Zahájení DB Transakce
            cursor.execute("BEGIN TRANSACTION")
            try:
                # 1. Vložení hlavičky a získání ID
                cursor.execute(sql_transakce_insert,
                               self.klient_id, self.datum, self.popis, self.doklad_cislo)
                self.id = cursor.fetchval()  # Uložení nově generovaného ID

                # 2. Vložení pohybů
                sql_pohyb_insert = (
                    "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) "
                    "VALUES (?, ?, ?, ?, ?)"
                )

                for pohyb in self.pohyby:
                    cursor.execute(sql_pohyb_insert,
                                   self.id, self.klient_id, pohyb.ucet, pohyb.smer, pohyb.castka)

                # Potvrzení DB Transakce (Commit)
                conn.commit()
                print(f"Transakce {self.id} úspěšně uložena.")

            except Exception as e:
                # Vrácení změn v případě chyby (Rollback)
                conn.rollback()
                print(f"Chyba při ukládání transakce. Změny vráceny: {e}")
                raise


class UcetniPohyb:
    """Model pro řádek v účetním žurnálu."""

    def __init__(self, klient_id, transakce_id, ucet, smer, castka, id=None):
        self.id = id
        self.klient_id = klient_id
        self.transakce_id = transakce_id
        self.ucet = ucet
        self.smer = smer  # 'MD' nebo 'D'
        self.castka = castka  # Vždy kladná


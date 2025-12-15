from collections import defaultdict
from core.database import execute_query, Database
from core.models import UcetniPohyb


class AccountingEngine:
    """Třída pro výpočet účetních dat a reportů."""

    def __init__(self, klient_id):
        self.klient_id = klient_id

    def get_zustaatek_uctu(self, ucet: str) -> float:
        # Původní kód je v pořádku
        sql_query = """
        SELECT 
            SUM(CASE WHEN smer = 'MD' THEN castka ELSE 0 END) AS SumaMD,
            SUM(CASE WHEN smer = 'D' THEN castka ELSE 0 END) AS SumaD
        FROM UcetniPohyby
        WHERE klient_id = ? AND ucet = ?
        """
        result = execute_query(sql_query, (self.klient_id, ucet))

        if result and result[0][0] is not None:
            suma_md = result[0][0]
            suma_d = result[0][1]
            zustatek = suma_md - suma_d
            return zustatek
        return 0.0

    def get_pohyby_uctu(self, ucet: str) -> list[UcetniPohyb]:
        # Původní kód je v pořádku
        sql_query = """
        SELECT id, transakce_id, klient_id, ucet, smer, castka
        FROM UcetniPohyby
        WHERE klient_id = ? AND ucet = ?
        ORDER BY id;
        """
        raw_pohyby = execute_query(sql_query, (self.klient_id, ucet))

        pohyby = []
        if raw_pohyby:
            for row in raw_pohyby:
                pohyby.append(UcetniPohyb(
                    id=row[0],
                    transakce_id=row[1],
                    klient_id=row[2],
                    ucet=row[3],
                    smer=row[4],
                    castka=float(row[5])
                ))
        return pohyby

    def spocti_zustatky(self):
        # Původní kód je v pořádku
        sql = """
        SELECT 
            ucet,
            SUM(CASE WHEN smer = 'MD' THEN castka ELSE 0 END) AS SumaMD,
            SUM(CASE WHEN smer = 'D' THEN castka ELSE 0 END) AS SumaD
        FROM UcetniPohyby
        WHERE klient_id = ?
        GROUP BY ucet
        """
        zustatky = defaultdict(float)
        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (self.klient_id,))
                raw_zustatky = cursor.fetchall()

            for ucet, suma_md, suma_d in raw_zustatky:
                zustatky[ucet] = suma_md - suma_d
            return dict(zustatky)
        except Exception as e:
            print(f"Chyba při výpočtu zůstatků: {e}")
            return {}

    # --- NOVÁ METODA PRO DPH ---
    def get_dph_sazby(self) -> dict:
        """Načte sazby DPH z DB a vrátí je jako slovník {procento: {účet_vstup, účet_výstup}}."""
        sql = "SELECT procento, ucet_dph_vstup, ucet_dph_vystup FROM SazbyDPH ORDER BY procento DESC"
        results = execute_query(sql)

        sazby = {}
        if results and results != []:  # Ošetření pro případ, že je tabulka prázdná
            for procento, ucet_vstup, ucet_vystup in results:
                # Používáme float(procento) jako klíč
                sazby[float(procento)] = {'vstup': ucet_vstup, 'vystup': ucet_vystup}

        # Pokud je tabulka prázdná, defaultně vrátíme alespoň 0%
        if not sazby:
            sazby[0.00] = {'vstup': '343', 'vystup': '343'}

        return sazby

    # --- PŘEPRACOVANÁ METODA PRO UKLÁDÁNÍ TRANSAKCE (Nyní s DPH) ---
    def save_transakce(self, datum, popis, doklad_cislo, ucet_md_zaklad, ucet_dal_zaklad, castka_bez_dph, sazba_dph,
                       smer_dph_popis):

        # 0. PŘÍPRAVA DAT DPH
        castka_zaklad = float(castka_bez_dph)

        if smer_dph_popis == 'Neučtovat' or float(sazba_dph) == 0.0:
            castka_dph = 0.0
            ucet_dph = None
        else:
            castka_dph = castka_zaklad * (float(sazba_dph) / 100)

            sazby_info = self.get_dph_sazby()
            info = sazby_info.get(float(sazba_dph))

            if not info:
                # Pokud se nepodařilo najít info o účtech DPH (i přes 0.00 fallback)
                raise ValueError(f"Neplatná nebo nenalezená sazba DPH: {sazba_dph}")

            # Určení účtu DPH (Vstup=MD; Výstup=D)
            if smer_dph_popis == 'DPH na VSTUPU (MD)':
                ucet_dph = info['vstup']
                smer_dph = 'MD'
                # Pohyb celkové částky (s DPH) na účet Dal
                ucet_protipolozka = ucet_dal_zaklad
                smer_protipolozka = 'D'
            else:  # DPH na VÝSTUPU (D)
                ucet_dph = info['vystup']
                smer_dph = 'D'
                # Pohyb celkové částky (s DPH) na účet Má Dáti
                ucet_protipolozka = ucet_md_zaklad
                smer_protipolozka = 'MD'

        castka_celkem = castka_zaklad + castka_dph

        sql_transakce = """
        INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo)
        VALUES (?, ?, ?, ?);
        """
        sql_pohyb = """
        INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka)
        VALUES (?, ?, ?, ?, ?);
        """

        try:
            with Database() as conn:
                cursor = conn.cursor()

                # --- 1. VLOŽENÍ HLAVIČKY TRANSAKCE + ZÍSKÁNÍ ID ---
                sql_insert_and_get_id = sql_transakce + "SELECT SCOPE_IDENTITY();"
                cursor.execute(sql_insert_and_get_id, (self.klient_id, datum, popis, doklad_cislo))

                if cursor.nextset():
                    transakce_id = cursor.fetchone()[0]
                else:
                    raise Exception("Nepodařilo se získat ID nově vložené transakce (SCOPE_IDENTITY selhalo).")

                # --- POHYBY ---

                # 1. POHYB ZÁKLADU (Základní účet je protipólem protipoložky)
                # Tj. pokud Celkem jde na DAL, Základ jde na MD (ucet_md_zaklad).
                ucet_zaklad = ucet_md_zaklad if smer_protipolozka == 'D' else ucet_dal_zaklad
                smer_zaklad = 'MD' if smer_protipolozka == 'D' else 'D'

                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_zaklad, smer_zaklad, castka_zaklad))

                # 2. POHYB DPH (Pokud se účtuje)
                if castka_dph > 0 and smer_dph_popis != 'Neučtovat':
                    cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_dph, smer_dph, castka_dph))

                # 3. PROTIPOLOŽKA (Celková částka, která se platí/přijímá)
                # Protipoložka je ta, která nenese základ ani DPH.
                cursor.execute(sql_pohyb,
                               (transakce_id, self.klient_id, ucet_protipolozka, smer_protipolozka, castka_celkem))

                conn.commit()
                return int(transakce_id)

        except Exception as e:
            if '_conn' in locals() and conn._conn:
                conn._conn.rollback()
            print(f"Chyba při ukládání transakce do DB: {e}")
            return None
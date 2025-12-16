from collections import defaultdict
from core.database import execute_query, Database
from core.models import UcetniPohyb  # Ponecháme, i když Třída Transakce není využita


class AccountingEngine:
    """Třída pro výpočet účetních dat a reportů."""

    def __init__(self, klient_id):
        self.klient_id = klient_id

    def get_ucet_nazev(self, ucet: str) -> str:
        """Načte název účtu z účtového rozvrhu."""
        sql = "SELECT nazev FROM UctovyRozvrh WHERE ucet = ?"
        result = execute_query(sql, (ucet,))
        return result[0][0] if result else ucet

    def get_zustatek_uctu(self, ucet: str) -> float:
        # Ponecháno, v pořádku
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
            # Zůstatek je MD - D
            zustatek = suma_md - suma_d
            return zustatek
        return 0.0

    def get_pohyby_uctu(self, ucet: str):
        """Načte detaily pohybů pro daný účet, včetně popisu a čísla dokladu."""
        sql_query = """
        SELECT 
            P.transakce_id, 
            P.smer, 
            P.castka, 
            T.doklad_cislo,        -- Nově: Číslo dokladu
            T.datum,               -- Nově: Datum transakce
            T.popis,               -- Nově: Popis transakce
            UR.nazev               -- Nově: Název účtu (i když je stejný)
        FROM UcetniPohyby AS P
        JOIN Transakce AS T ON P.transakce_id = T.id
        JOIN UctovyRozvrh AS UR ON P.ucet = UR.ucet
        WHERE P.klient_id = ? AND P.ucet = ?
        ORDER BY T.datum DESC, P.id;
        """
        # Vrátíme obohacená data jako list of dicts, protože model UcetniPohyb je příliš jednoduchý
        results = execute_query(sql_query, (self.klient_id, ucet))

        pohyby_list = []
        if results:
            for row in results:
                pohyby_list.append({
                    'Transakce ID': row[0],
                    'Směr': row[1],
                    'Částka': float(row[2]),
                    'Doklad Číslo': row[3],
                    'Datum': row[4].strftime('%Y-%m-%d'),
                    'Popis Transakce': row[5],
                    'Název Účtu': row[6]
                })
        return pohyby_list

    def spocti_zustatky(self):
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
        for row in results:
            # Ujistěte se, že procento je správně převedeno na float
            procento = float(row[0])
            sazby[procento] = {
                'vstup': row[1],
                'vystup': row[2]
            }
        return sazby

    def spocti_prehled_dph(self) -> dict:
        """
        Spočítá zůstatek pro každou sazbu DPH (Vstup vs. Výstup) a celkovou daňovou povinnost.
        Vrací slovník s celkovým výsledkem a detaily po sazbách.

        POZNÁMKA: get_zustatek_uctu vrací zůstatek jako decimal.Decimal,
        proto musíme vše konvertovat na float pro sčítání (nebo použít decimal modul).
        Zde volíme float pro zjednodušení zobrazení.
        """

        prehled = {}
        # Inicializujeme jako float, proto budeme potřebovat konverzi při sčítání.
        celkova_povinnost = 0.0

        # 1. Získání definice sazeb DPH z DB
        sazby_dict = self.get_dph_sazby()

        for procento, ucty in sazby_dict.items():
            ucet_vstup = ucty['vstup']
            ucet_vystup = ucty['vystup']

            # 2. Získání zůstatků (vrací decimal.Decimal)
            zustatek_vstup = self.get_zustatek_uctu(ucet_vstup)
            zustatek_vystup = self.get_zustatek_uctu(ucet_vystup)

            # 3. Konverze na float PŘED matematickými operacemi (řeší TypeError)
            zustatek_vstup_f = float(zustatek_vstup)
            zustatek_vystup_f = float(zustatek_vystup)

            # 4. Výpočet rozdílu
            # DPH Povinnost = Závazek (343.2.xx, záporný zůstatek) + Pohledávka (343.1.xx, kladný zůstatek)
            # Součet dává čistý rozdíl. Kladné číslo = nedoplatek k úhradě.
            rozdil_sazby = zustatek_vstup_f + zustatek_vystup_f

            # 5. Uložení výsledků pro danou sazbu
            prehled[procento] = {
                'vstup': zustatek_vstup_f,
                'vystup': zustatek_vystup_f,
                'rozdil': rozdil_sazby
            }

            # 6. Agregace celkové povinnosti (obě strany jsou float)
            celkova_povinnost += rozdil_sazby

        prehled['CELKEM'] = celkova_povinnost
        return prehled

    # --- PŘEPRACOVANÁ METODA PRO UKLÁDÁNÍ TRANSAKCE (Nyní s DPH) ---
    def save_transakce(self, datum, popis, doklad_cislo, ucet_md_zaklad, ucet_dal_zaklad, castka_bez_dph, sazba_dph,
                       smer_dph_popis):

        # 0. PŘÍPRAVA DAT DPH
        castka_zaklad = float(castka_bez_dph)
        castka_dph = 0.0

        if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:

            castka_dph = castka_zaklad * (float(sazba_dph) / 100)
            sazby_info = self.get_dph_sazby()
            info = sazby_info.get(float(sazba_dph))

            if not info:
                raise ValueError(f"Nenalezeny účty pro sazbu DPH: {sazba_dph}")

            # Určení účtu a směru DPH
            if smer_dph_popis == 'DPH na VSTUPU (MD)':
                ucet_dph = info['vstup']
                smer_dph = 'MD'
                # Protipoložka, která nese celkem (např. 321) je na DAL
                ucet_protipolozka = ucet_dal_zaklad
                smer_protipolozka = 'D'
            else:  # DPH na VÝSTUPU (D)
                ucet_dph = info['vystup']
                smer_dph = 'D'
                # Protipoložka, která nese celkem (např. 221) je na MD
                ucet_protipolozka = ucet_md_zaklad
                smer_protipolozka = 'MD' # <--- ZAJIŠTĚNO, ŽE JE DEFINOVÁNO VŽDY

        else:
            # Neúčtuje se DPH, transakce je jen na základní částku
            castka_dph = 0.0
            ucet_dph = None

            # Nastavíme základní směr účtování (musí se vybrat jeden z MD/DAL)
            # Předpoklad: Při nákupu je protipoložka D (závazek), při prodeji MD (banka/pohledávka)
            if ucet_md_zaklad in ['511', '501']:  # Typický MD náklad
                ucet_protipolozka = ucet_dal_zaklad  # 321, 221
                smer_protipolozka = 'D' # <--- ZDE BYLO DEFINOVÁNO
            else:  # Typický D výnos (602)
                ucet_protipolozka = ucet_md_zaklad  # 221, 311
                smer_protipolozka = 'MD' # <--- TOTO BYLO PŘIDÁNO!


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

                # Získání ID
                cursor.nextset()
                transakce_id = cursor.fetchone()[0]

                # --- POHYBY ---

                # 1. POHYB ZÁKLADU
                # Určíme účet základu (ten, který NENÍ protipoložkou) a jeho směr (opak protipoložky)
                ucet_zaklad = ucet_md_zaklad if smer_protipolozka == 'D' else ucet_dal_zaklad
                smer_zaklad = 'MD' if smer_protipolozka == 'D' else 'D'

                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_zaklad, smer_zaklad, castka_zaklad))

                # 2. POHYB DPH (Pokud se účtuje)
                if castka_dph > 0 and ucet_dph:
                    cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_dph, smer_dph, castka_dph))

                # 3. PROTIPOLOŽKA (Celková částka nebo Základ)
                # Použijeme castka_celkem, i když DPH=0, protože castka_celkem = castka_zaklad + 0
                cursor.execute(sql_pohyb,
                               (transakce_id, self.klient_id, ucet_protipolozka, smer_protipolozka, castka_celkem))

                conn.commit()
                return int(transakce_id)

        except Exception as e:
            if '_conn' in locals() and conn._conn:
                conn._conn.rollback()
            print(f"Chyba při ukládání transakce do DB: {e}")
            return None
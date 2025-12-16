from collections import defaultdict
from core.database import execute_query, Database
from core.models import UcetniPohyb
from decimal import Decimal
import pandas as pd


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

    def get_pohyby_uctu(self, ucet, datum_od=None, datum_do=None):
        """
        Získá detailní pohyby pro konkrétní účet s volitelným časovým filtrem.

        Parametry:
        - ucet (str): Účet (včetně analytiky).
        - datum_od (date/str): Počáteční datum období (včetně).
        - datum_do (date/str): Koncové datum období (včetně).
        """

        # Vybíráme všechny důležité sloupce pro zobrazení v Historii
        sql = """
            SELECT 
                T.datum,
                T.doklad_cislo,
                T.popis AS PopisTransakce,
                P.smer,
                P.castka,
                P.ucet AS ProtipolozkaUcet,
                (SELECT nazev FROM UctovyRozvrh WHERE ucet = P.ucet) AS NazevProtipolozky
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id  
            WHERE T.klient_id = ? 
            AND P.ucet = ? 
            """

        params = [self.klient_id, ucet]

        # --- APLIKACE ČASOVÉHO FILTRU ---
        if datum_od:
            # Převedeme na string, pokud Streamlit vrací date objekt
            datum_od_str = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(datum_od_str)

        if datum_do:
            # Převedeme na string, pokud Streamlit vrací date objekt
            datum_do_str = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(datum_do_str)
        # --- KONEC ČASOVÉHO FILTRU ---

        # Seřadíme podle data pro správné zobrazení historie
        sql += " ORDER BY T.datum, T.id"

        try:
            with Database() as conn:
                df = pd.read_sql_query(sql, conn, params=tuple(params))

            if df.empty:
                return []

            # Přejmenování sloupců pro lepší výstup ve Streamlit (jako to děláte v app.py)
            df.columns = [
                'Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka',
                'Protipolozka Ucet', 'Název Protipoložky'
            ]

            # Ponecháme jen sloupce, které chceme vracet do UI pro finální zobrazení
            df = df[['Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka', 'Název Protipoložky']]

            # Pro zjednodušení kódu v UI/app.py přejmenujeme Název Protipoložky na "Název Účtu"
            # aby to odpovídalo očekávané logice:
            df.rename(columns={'Název Protipoložky': 'Název Účtu'}, inplace=True)

            # Převod na list slovníků pro snadnou práci ve Streamlit
            return df.to_dict('records')

        except Exception as e:
            print(f"Chyba při získávání pohybů pro účet {ucet}: {e}")
            return []

    def spocti_zustatky(self, datum_od=None, datum_do=None):
        """
        Spočítá zůstatky všech účtů k danému datu (datum_do).
        Zůstatek je kumulativní (počítá se od počátku historie do datum_do).
        datum_od se ignoruje, protože zůstatek je vždy kumulativní.
        """
        zustatky = defaultdict(float)
        # Základní SQL dotaz pro kumulativní součty
        sql = """
                SELECT 
                    P.ucet,
                    SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) AS SumaMD,
                    SUM(CASE WHEN P.smer = 'D' THEN P.castka ELSE 0 END) AS SumaD
                FROM UcetniPohyby P
                JOIN Transakce T ON T.id = P.transakce_id
                WHERE P.klient_id = ?
                """

        params = [self.klient_id]

        # --- APLIKACE FILTRU K DATU (datum_do) ---
        if datum_od:
            datum_od_str = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(datum_od_str)

        if datum_do:
            # Přidáme podmínku, že datum z tabulky T (Transakce) musí být menší nebo rovno
            datum_do_str = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(datum_do_str)

        sql += " GROUP BY P.ucet"

        zustatky = defaultdict(float)

        try:
            # Předpokládáme, že Database() je správně definovaný kontextový manažer
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))  # Předáváme parametry jako tuple
                raw_zustatky = cursor.fetchall()

            for ucet, suma_md, suma_d in raw_zustatky:
                # Zůstatek = MD (Aktivum/Náklad) - D (Pasivum/Výnos)
                zustatky[ucet] = suma_md - suma_d

            return dict(zustatky)

        except Exception as e:
            # Měli bychom tisknout logy do systémového logu, ne jen do konzole
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

    # soubor: core/accounting_logic.py

    # ... (uvnitř třídy AccountingEngine) ...

    def spocti_prehled_dph(self, datum_od=None, datum_do=None):
        """
        Spočítá souhrnnou daňovou povinnost DPH pro dané období.
        Vyhledává pohyby na všech DPH účtech (definovaných v sazbách)
        a sčítá jejich hodnoty v rámci zvoleného časového rozmezí.
        """
        dph_sazby = self.get_dph_sazby()
        prehled = defaultdict(lambda: {'vstup': Decimal('0.0'), 'vystup': Decimal('0.0'), 'rozdil': Decimal('0.0')})
        celkem_rozdil = Decimal('0.0')

        # Shromáždíme všechny DPH účty pro SQL dotaz
        vsechny_dph_ucty = []
        for sazba_dict in dph_sazby.values():
            if sazba_dict['vstup']: vsechny_dph_ucty.append(sazba_dict['vstup'])
            if sazba_dict['vystup']: vsechny_dph_ucty.append(sazba_dict['vystup'])

        # Odstranění duplicit a None hodnot
        vsechny_dph_ucty = list(set(filter(None, vsechny_dph_ucty)))

        if not vsechny_dph_ucty:
            # Pokud nejsou definovány DPH účty, vrátíme nulu
            return {'CELKEM': 0.0}

        # Sestavení klauzule WHERE pro DPH účty (Používáme LIKE pro pokrytí analytik, např. 343.1%)
        ucet_patterns = [f"{u}%" for u in vsechny_dph_ucty]
        placeholders = " OR ".join(["P.ucet LIKE ?" for _ in ucet_patterns])

        sql = f"""
                SELECT 
                    P.ucet, 
                    P.smer, 
                    P.castka
                FROM UcetniPohyby P
                JOIN Transakce T ON T.id = P.transakce_id
                WHERE P.klient_id = ? 
                AND ({placeholders})
                """

        params = [self.klient_id] + ucet_patterns

        # --- APLIKACE ČASOVÉHO FILTRU ---
        if datum_od:
            d_od = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(d_od)

        if datum_do:
            d_do = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(d_do)

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                pohyby = cursor.fetchall()

            # Agregace výsledků v Pythonu (flexibilnější než složité SQL CASE statementy)
            for ucet, smer, castka in pohyby:
                castka_dec = Decimal(str(castka))  # Bezpečný převod na Decimal

                # Najdeme, do jaké sazby a typu (vstup/výstup) tento účet patří
                found = False
                for sazba, ucty in dph_sazby.items():
                    # Kontrola VSTUPU (např. 343.100 startswith 343.1)
                    if ucty['vstup'] and ucet.startswith(ucty['vstup']) and smer == 'MD':
                        prehled[sazba]['vstup'] += castka_dec
                        found = True
                        break
                    # Kontrola VÝSTUPU
                    elif ucty['vystup'] and ucet.startswith(ucty['vystup']) and smer == 'D':
                        prehled[sazba]['vystup'] += castka_dec
                        found = True
                        break

                # Pokud účet nebyl nalezen v konfiguraci (např. ruční účtování na špatnou analytiku), ignorujeme ho nebo logujeme

            # Finální výpočet rozdílů
            for sazba, data in prehled.items():
                # Daňová povinnost = Výstup (D) - Vstup (MD)
                r = data['vystup'] - data['vstup']
                data['rozdil'] = r
                celkem_rozdil += r

            prehled['CELKEM'] = celkem_rozdil
            return dict(prehled)

        except Exception as e:
            print(f"SQL Error DPH: {e}")
            return {'CELKEM': 0.0}

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
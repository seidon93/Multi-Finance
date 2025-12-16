import sys
import os
from datetime import date
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal

# Zajištění, že se importují moduly z nadřazeného adresáře (core)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, os.pardir))

from dotenv import load_dotenv


# --- FAKE ENGINE PRO TESTOVÁNÍ KÓDU BEZ DATABÁZE (PRO VIZUALIZACI) ---
class AccountingEngine:
    """Simuluje klíčové metody pro ukázku UI."""

    def __init__(self, klient_id):
        pass

    def get_dph_sazby(self):
        return {21.0: {'vstup': '343.1.21', 'vystup': '343.2.21'}, 0.0: {'vstup': '343.1.00', 'vystup': '343.2.00'}}

    def get_ucet_nazev(self, ucet):
        return f"Název účtu {ucet}"

    # TATO METODA JE NÁZVU, KTERÝ SE POUŽÍVÁ V KÓDU (spocitej_zustatky)
    def spocitej_zustatky(self, datum_od=None, datum_do=None):
        return {'221': 150000.0, '321': -126671.08, '511': 50000.0, '343.2.21': -21000.0}

    def save_transakce(self, **kwargs):
        return 123

    def spocti_prehled_dph(self, datum_od=None, datum_do=None):
        return {'CELKEM': Decimal('12500.00'),
                21.0: {'vstup': Decimal('10000.00'), 'vystup': Decimal('22500.00'), 'rozdil': Decimal('12500.00')}}

    def get_pohyby_uctu(self, ucet, datum_od=None, datum_do=None):
        return [
            {'Datum': date(2025, 12, 1), 'Doklad Číslo': 'F-100', 'Popis Transakce': 'Příjem faktury',
             'Částka': -25000.00, 'Název Účtu': 'Banka'},
            {'Datum': date(2025, 12, 10), 'Doklad Číslo': 'FV-01', 'Popis Transakce': 'Úhrada faktury',
             'Částka': 15000.00, 'Název Účtu': 'Pokladna'}
        ]


# --- KONEC FAKE ENGINE ---

load_dotenv()
DB_PASSWORD = os.environ.get("DB_PASSWORD")
KLIENT_ID = 1
engine = AccountingEngine(klient_id=KLIENT_ID)

# --- GLOBÁLNÍ CSS STYLING ---
st.markdown(
    """
    <style>
    /* Obecné styly pro mřížku */
    [data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 150px;
        max-width: 300px;
    }

    /* Vizuální styly pro text v hlavičce Historie a účty */
    .zustatek-kladny { color: #28a745 !important; font-size: 1.15em !important; font-weight: bold !important; }
    .zustatek-zaporny { color: #dc3545 !important; font-size: 1.15em !important; font-weight: bold !important; }
    .ucet-nazev { color: #007bff !important; font-size: 1.25em !important; font-weight: bold !important; margin-bottom: 0px; }
    p { margin-bottom: 5px; margin-top: 5px; }

    /* --- PRAVIDLA PRO TLAČÍTKO RESET (ČERVENÁ BARVA - SPUŠTĚNO PŘES type="primary") --- */
    /* Odstraněn margin-top, nahrazeno vertical_alignment v Pythonu */
    div.stButton > button[kind="primary"] {
        background-color: #A93226 !important; /* Tmavě červená */
        color: white !important;
        border-radius: 5px;
        border: 1px solid #A93226 !important;
        transition: background-color 0.2s ease;
    }

    div.stButton > button[kind="primary"]:hover {
        background-color: #C0392B !important; 
        color: white !important; 
        border: 1px solid #C0392B !important;
    }
    div.stButton > button[kind="primary"]:active {
        background-color: #8D2A1F !important; 
        color: white !important; 
        border: 1px solid #8D2A1F !important;
    }

    /* Fallback selektor pro starší verze Streamlit */
    div.stButton > button[data-testid="baseButton-primary"] {
        background-color: #A93226 !important;
        border-color: #A93226 !important;
    }

    /* --- PRAVIDLA PRO TLAČÍTKO 'CELÁ HISTORIE' (ZELENÁ) --- */
    div.stButton > button[key*='filter_vse_r'] {
        background-color: #27AE60 !important; /* Tmavě zelená */
        color: white !important;
        border: 1px solid #27AE60 !important;
        transition: background-color 0.2s ease;
    }
    div.stButton > button[key*='filter_vse_r']:hover {
        background-color: #2ECC71 !important;
        border: 1px solid #2ECC71 !important;
    }
    div.stButton > button[key*='filter_vse_r']:active {
        background-color: #1E8449 !important;
        border: 1px solid #1E8449 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# --- KONEC GLOBÁLNÍHO CSS ---


def zobrazit_header():
    """Vytvoří hlavičku a navigační menu."""
    st.title("💰 Multi-Finance Účetní Systém")
    st.sidebar.title("Navigace")

    vyber = st.sidebar.radio(
        "Zvolte Modul:",
        ("Nová Transakce", "Přehled Účtů", "Přehled DPH", "Historie")
    )
    return vyber


def formular_nova_transakce():
    st.header("Vytvořit Novou Transakci")

    with st.form("transakce_form"):
        # --- HLAVIČKA TRANSAKCE ---
        col1, col2 = st.columns(2)
        doklad_cislo = col1.text_input("Číslo Dokladu", value=f"FP-{KLIENT_ID}-")
        datum_transakce = col2.date_input("Datum Transakce", value=date.today())
        popis = st.text_area("Popis Transakce", placeholder="Popis účetní operace.")

        st.subheader("Účetní Pohyby Základu")

        # --- Pohyby Základu ---
        col_zaklad, col_protipolozka = st.columns(2)

        ucet_md_zaklad = col_zaklad.text_input("Účet MD (Základ / Celkem)", value="511")
        ucet_dal_zaklad = col_protipolozka.text_input("Účet D (Základ / Celkem)", value="321")
        castka_bez_dph = st.number_input("Částka ZÁKLADU (bez DPH)", min_value=0.01, format="%.2f")

        st.subheader("Nastavení DPH")

        # 1. Získání seznamu sazeb DPH
        dph_sazby_dict = engine.get_dph_sazby()
        dph_sazby_options = sorted(list(dph_sazby_dict.keys()), reverse=True)

        # 2. Výběr Sazby
        vybrana_sazba = st.selectbox(
            "Sazba DPH (%)",
            options=dph_sazby_options,
            index=dph_sazby_options.index(0.00) if 0.00 in dph_sazby_options else 0
        )

        # 3. Směr pohybu DPH
        smer_dph = st.radio(
            "Směr DPH",
            options=['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'],
            horizontal=True
        )

        submitted = st.form_submit_button("Uložit Transakci")

        if submitted:
            try:
                # --- VOLÁNÍ METODY S KOMPLETNÍMI DATY ---
                transakce_id = engine.save_transakce(
                    datum=datum_transakce,
                    popis=popis,
                    doklad_cislo=doklad_cislo,
                    ucet_md_zaklad=ucet_md_zaklad,
                    ucet_dal_zaklad=ucet_dal_zaklad,
                    castka_bez_dph=castka_bez_dph,
                    sazba_dph=vybrana_sazba,
                    smer_dph_popis=smer_dph
                )

                if transakce_id:
                    st.success(f"Transakce {doklad_cislo} úspěšně uložena s ID {transakce_id}.")
                else:
                    st.error("Chyba při ukládání transakce. Zkontrolujte logy (terminál).")

            except Exception as e:
                st.exception(f"FATÁLNÍ CHYBA: {e}")


def zobrazit_prehled_uctu():
    st.header("Přehled Zůstatků na Účtech")

    # --- VLOŽENÍ ČASOVÉHO FILTRU ---
    date_from, date_to = time_filter_ui()
    st.markdown("---")  # Oddělení filtru od přehledu

    # Získání zůstatků s filtrem (OPRAVENO: volá spocitej_zustatky)
    zustatky_all = engine.spocitej_zustatky(datum_od=date_from, datum_do=date_to)

    # --- 1. SEZNAM SLEDOVANÝCH ÚČTŮ (FILTROVANÝ PŘEHLED) ---
    st.subheader("Přehled Sledovaných Účtů (Klíčová Analytika)")

    sledovane_ucty = [
        '221', '311', '602', '511', '321',
        '343.1.21', '343.2.21', '343.1.12', '343.2.12', '343.1.00', '343.2.00',
        '343.1', '343.2'
    ]

    data = []
    for ucet in sledovane_ucty:
        # POUŽITÍ NOVÉHO FILTROVANÉHO ZŮSTATKU
        zustatek = zustatky_all.get(ucet, 0.0)
        nazev = engine.get_ucet_nazev(ucet)

        # Zobrazíme jen účty s nenulovým zůstatkem NEBO klíčové syntetické účty
        if abs(zustatek) > 0.005 or ucet in ['221', '311', '321', '511', '602']:
            data.append({
                'Účet': ucet,
                'Název': nazev,
                'Zůstatek': zustatek
            })

    # Formátování a zobrazení tabulky
    df = pd.DataFrame(data)
    if not df.empty:
        df['Zůstatek'] = df['Zůstatek'].map('{:,.2f} Kč'.format)
        st.table(df)
    else:
        st.info("Žádné zůstatky na sledovaných účtech v zadaném období.")

    # --- 2. SYNTERICKÁ ÚČETNÍ KNIHA (AGREGACE) ---
    st.subheader("Syntetická Účetní Kniha (Všechny zůstatky)")

    if st.button("Obnovit Agregované Zůstatky"):
        # VOLÁNÍ S FILTREM I ZDE (OPRAVENO: volá spocitej_zustatky)
        zustatky_data = engine.spocitej_zustatky(datum_od=date_from, datum_do=date_to)

        if zustatky_data:
            zustatky_df = pd.DataFrame(
                zustatky_data.items(),
                columns=["Účet", "Zůstatek"]
            )

            # 1. Přidání názvů účtů
            zustatky_df['Název'] = zustatky_df['Účet'].apply(engine.get_ucet_nazev)

            # 2. FILTROVÁNÍ: Použijeme absolutní hodnotu PŘED formátováním na řetězec
            zustatky_df['AbsZustatek'] = zustatky_df['Zůstatek'].abs()
            zustatky_df = zustatky_df[zustatky_df['AbsZustatek'] > 0.005]
            zustatky_df.drop(columns=['AbsZustatek'], inplace=True)

            # 3. FORMÁTOVÁNÍ: Až nyní převedeme sloupec 'Zůstatek' na řetězec s měnou
            zustatky_df["Zůstatek"] = zustatky_df["Zůstatek"].map('{:,.2f} Kč'.format)

            # 4. Řazení a zobrazení
            zustatky_df = zustatky_df.sort_values(by='Účet')
            zustatky_df = zustatky_df[['Účet', 'Název', 'Zůstatek']]

            st.dataframe(zustatky_df, hide_index=True, width='stretch')
        else:
            st.warning("Nelze načíst nebo spočítat agregované zůstatky v zadaném období.")


def zobrazit_prehled_dph():
    import pandas as pd
    from decimal import Decimal  # Zajistit import Decimal, pokud není globální

    st.header("Daňová Povinnost DPH")

    # 1. Získání časového filtru
    date_from, date_to = time_filter_ui()
    st.markdown("---")

    # --- Inicializace Session State pro DPH data ---
    if 'dph_data' not in st.session_state:
        st.session_state['dph_data'] = None
    if 'dph_celkem' not in st.session_state:
        st.session_state['dph_celkem'] = Decimal('0.0')

    # --- Logika pro automatický výpočet ---

    # Uložení aktuálního filtru do stavu pro detekci změn
    current_filter = (date_from, date_to)

    # Detekce změny filtru nebo prvního načtení
    if st.session_state.get('last_dph_filter') != current_filter:
        st.session_state['last_dph_filter'] = current_filter

        # Spustit výpočet pouze pokud jsou platná data
        if date_from and date_to:
            with st.spinner(f"Počítám DPH povinnost pro období od {date_from} do {date_to}..."):
                dph_data = engine.spocti_prehled_dph(datum_od=date_from, datum_do=date_to)

                # Uložit do stavu
                st.session_state['dph_celkem'] = dph_data.pop('CELKEM', Decimal('0.0'))
                st.session_state['dph_data'] = dph_data
        else:
            st.session_state['dph_data'] = None
            st.session_state['dph_celkem'] = Decimal('0.0')

    # --- Zobrazení výsledků ---

    dph_data = st.session_state['dph_data']
    celkem = st.session_state['dph_celkem']

    if dph_data is None:
        st.info("Vyberte prosím časové rozmezí pro výpočet DPH.")
        return

    # Dynamická hlavička pro období
    st.info(f"Přehled DPH za období: **{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}**")

    # --- Tabulka zůstatků po sazbách ---
    st.subheader("Detailní Přehled po Sazbách")

    detail_data = []

    # Získání mapování účtů pro hlavičky tabulky
    dph_ucty_map = engine.get_dph_sazby()

    for sazba, data in dph_data.items():
        if sazba != 'CELKEM':
            # Získání názvů analytických účtů pro lepší kontext
            ucty_map = dph_ucty_map.get(sazba, {'vstup': 'N/A', 'vystup': 'N/A'})

            # Zajištění, že všechny hodnoty jsou Decimal před vložením
            vstup = data.get('vstup', Decimal('0.0'))
            vystup = data.get('vystup', Decimal('0.0'))
            rozdil = data.get('rozdil', Decimal('0.0'))

            detail_data.append({
                'Sazba (%)': f"{sazba:.2f}",
                f'DPH VSTUP ({ucty_map["vstup"]})': vstup,
                f'DPH VÝSTUP ({ucty_map["vystup"]})': vystup,
                'Rozdíl DPH (Závazek - Pohledávka)': rozdil
            })

    if not detail_data:
        st.warning("Nejsou nalezeny žádné DPH pohyby pro toto období.")

    else:
        df_detail = pd.DataFrame(detail_data)

        # --- Formátování: Decimal to string ---
        df_detail = df_detail.fillna(Decimal('0.0'))

        for col in df_detail.columns:
            if col not in ['Sazba (%)']:
                # Používáme lambda s kontrolou typu, protože Decimal se formátuje přímo
                df_detail[col] = df_detail[col].apply(lambda x: f'{x:,.2f} Kč')

        # --- ZOBRAZENÍ TABULKY ---
        st.dataframe(
            df_detail,
            hide_index=True,
            width='stretch'
        )

    # --- Celková povinnost ---
    st.subheader("Celková Daňová Povinnost")

    # Barvy a text pro Celkovou Povinnost
    if celkem > Decimal('0.005'):  # Použít malou toleranci pro Decimal porovnání
        typ = "NEDOPLATEK (K ÚHRADĚ)"
        barva = "red"
    elif celkem < Decimal('-0.005'):
        typ = "PŘEPLATEK (K VRÁCENÍ)"
        barva = "green"
    else:
        typ = "NULOVÁ POVINNOST"
        barva = "blue"


def zobrazit_historii_uctu():
    import pandas as pd

    st.header("Historie Účtu (Detailní Přehled)")

    date_from, date_to = time_filter_ui()

    # OPRAVENO: volá spocitej_zustatky
    zustatky_all_filtrovane = engine.spocitej_zustatky(datum_od=None, datum_do=date_to)
    zustatky_all_komplet = engine.spocitej_zustatky()

    seznam_uctu_s_pohybem = [ucet for ucet, zustatek in zustatky_all_komplet.items() if abs(zustatek) > 0.005]
    seznam_uctu_s_pohybem = sorted(seznam_uctu_s_pohybem)

    if not seznam_uctu_s_pohybem:
        st.info("Žádný účet nemá aktuálně nenulový zůstatek pro zobrazení historie.")
        return

    # --- ZABEZPEČENÍ VÝBĚRU ÚČTŮ V SESSION STATE ---
    if 'vybrane_ucty' not in st.session_state:
        # Nastavíme defaultní výběr při prvním načtení
        default_vyber = [u for u in ['221', '321', '311'] if u in seznam_uctu_s_pohybem] or []
        st.session_state['vybrane_ucty'] = default_vyber

    st.subheader("1. Výběr účtů pro detailní přehled")

    # Nyní používáme st.session_state['vybrane_ucty'] jako default
    vybrane_ucty_k_zobrazeni = st.multiselect(
        "Vyberte účty, jejichž historii chcete zobrazit:",
        options=seznam_uctu_s_pohybem,
        default=st.session_state['vybrane_ucty'],  # <- Používáme uloženou hodnotu
        key='historie_multiselect_ucet'
    )

    # Důležité: Uložíme novou hodnotu zpět, i když Streamlit to dělá automaticky s klíčem,
    # pro zajištění, že se po rerunu použije správná sada.
    st.session_state['vybrane_ucty'] = vybrane_ucty_k_zobrazeni
    # --- KONEC ZABEZPEČENÍ ---

    if not vybrane_ucty_k_zobrazeni:
        st.warning("Prosím, vyberte alespoň jeden účet k zobrazení.")
        return

    st.subheader("2. Detailní pohyby")

    for ucet_k_zobrazeni in vybrane_ucty_k_zobrazeni:

        pohyby = engine.get_pohyby_uctu(ucet_k_zobrazeni, datum_od=date_from, datum_do=date_to)
        aktualni_zustatek = zustatky_all_filtrovane.get(ucet_k_zobrazeni, 0)

        css_class_zustatek = "zustatek-kladny" if aktualni_zustatek >= 0 else "zustatek-zaporny"

        st.markdown(
            f'<p class="ucet-nazev">'
            f'Pohyby účtu {ucet_k_zobrazeni} ({engine.get_ucet_nazev(ucet_k_zobrazeni)})'
            f'</p>'
            f'<p>Aktuální zůstatek: <span class="{css_class_zustatek}">{aktualni_zustatek:,.2f} Kč</span></p>',
            unsafe_allow_html=True
        )

        if pohyby:
            df_pohyby = pd.DataFrame(pohyby)

            if 'Částka' in df_pohyby.columns:
                try:
                    df_pohyby['Částka'] = df_pohyby['Částka'].astype(float)
                except:
                    pass

                df_pohyby['Částka'] = df_pohyby['Částka'].apply(lambda x: f'{x:,.2f} Kč')

            required_cols = ['Datum', 'Doklad Číslo', 'Popis Transakce', 'Částka']
            if 'Název Účtu' in df_pohyby.columns:
                required_cols.append('Název Účtu')

            df_pohyby = df_pohyby[required_cols]
            st.dataframe(df_pohyby, width='stretch', hide_index=True)

        else:
            st.info(f"Na účtu {ucet_k_zobrazeni} nebyly nalezeny žádné pohyby v období od {date_from} do {date_to}.")


def time_filter_ui():
    """Vykreslí tlačítka a výběr rozmezí ve stabilním layoutu (2 řádky s vizuálním zarovnáním)."""
    st.subheader("Filtrování časového rozmezí")

    dnes = date.today()

    # Uložení stavu vybraných dat do session state
    if 'filter_date_from' not in st.session_state:
        st.session_state['filter_date_from'] = None
    if 'filter_date_to' not in st.session_state:
        st.session_state['filter_date_to'] = None

    # --- Definice funkcí pro časové skoky ---
    def set_dates(d_from, d_to):
        st.session_state['filter_date_from'] = d_from
        st.session_state['filter_date_to'] = d_to
        # Není třeba st.rerun(), protože st.date_input to spouští automaticky

    def get_start_of_week(d):
        return d - timedelta(days=d.weekday())

    def get_start_of_month(d):
        return d.replace(day=1)

    def get_start_of_year(d):
        return d.replace(month=1, day=1)

    def get_last_week():
        start_this_week = get_start_of_week(dnes)
        end_last_week = start_this_week - timedelta(days=1)
        start_last_week = get_start_of_week(end_last_week)
        return start_last_week, end_last_week

    # --- HLAVNÍ KONTEJNER (Sjednocuje tlačítka i inputy do jednoho rámečku) ---
    with st.container(border=True):

        # --- ŘÁDEK 1: RYCHLÁ VOLBA (6 TLAČÍTEK) ---
        col_dnes, col_tyden, col_minutyden, col_mesic, col_rok, col_vse = st.columns(6)

        # Používáme st.rerun() přímo v set_dates, takže můžeme tlačítka zjednodušit
        if col_dnes.button("Dnes", key='filter_dnes_r1', use_container_width=True):
            set_dates(dnes, dnes)
            st.rerun()  # Přidání rerun pro okamžitou změnu filtru u tlačítek
        if col_tyden.button("Tento týden", key='filter_tyden_r1', use_container_width=True):
            start_week = get_start_of_week(dnes)
            set_dates(start_week, dnes)
            st.rerun()
        if col_minutyden.button("Minulý týden", key='filter_minutyden_r1', use_container_width=True):
            start_lw, end_lw = get_last_week()
            set_dates(start_lw, end_lw)
            st.rerun()
        if col_mesic.button("Měsíc", key='filter_mesic_r1', use_container_width=True):
            start_month = get_start_of_month(dnes)
            set_dates(start_month, dnes)
            st.rerun()
        if col_rok.button("Aktuální rok", key='filter_rok_r1', use_container_width=True):
            start_year = get_start_of_year(dnes)
            set_dates(start_year, dnes)
            st.rerun()
        if col_vse.button("Celá historie", key='filter_vse_r1', use_container_width=True):
            set_dates(None, None)
            st.rerun()

        # --- ODDĚLOVAČ UVNITŘ KONTEJNERU ---
        st.markdown("---")

        # --- ŘÁDEK 2: RUČNÍ VÝBĚR A RESET ---
        # vertical_alignment="bottom" zajistí, že tlačítko Reset bude dole zarovnané s inputy
        # Nastavení poměrů sloupců: [1.2, 1.2, 0.7] (Datum OD, Datum DO, Reset)
        col_from, col_to, col_reset = st.columns([1.2, 1.2, 0.7], vertical_alignment="bottom")

        # Uložíme původní stav před změnou, abychom detekovali, zda uživatel input změnil
        # Tím zabráníme zbytečnému rerun, pokud se pouze vybere stejná hodnota.
        old_date_from = st.session_state['filter_date_from']
        old_date_to = st.session_state['filter_date_to']

        date_from_input = col_from.date_input(
            "Datum OD",
            value=old_date_from if old_date_from else None,
            key='input_date_from'
        )
        date_to_input = col_to.date_input(
            "Datum DO",
            value=old_date_to if old_date_to else None,
            key='input_date_to'
        )

        # Tlačítko Reset je typu 'primary' (červené díky CSS)
        if col_reset.button("Reset Filtru", key='filter_reset', use_container_width=True, type="primary"):
            set_dates(None, None)
            st.rerun()

    # --- Zpracování ručního výběru ---
    # Pokud se hodnota v date_input změní, uložíme ji a Streamlit automaticky spustí rerun.
    if date_from_input != old_date_from or date_to_input != old_date_to:
        st.session_state['filter_date_from'] = date_from_input
        st.session_state['filter_date_to'] = date_to_input
        # Není třeba st.rerun(), protože date_input to dělá za nás

    return st.session_state['filter_date_from'], st.session_state['filter_date_to']


# --- Hlavní spouštěcí smyčka Streamlit ---
if __name__ == "__main__":
    modul = zobrazit_header()

    if modul == "Nová Transakce":
        formular_nova_transakce()
    elif modul == "Přehled Účtů":
        zobrazit_prehled_uctu()
    elif modul == "Přehled DPH":
        zobrazit_prehled_dph()
    elif modul == "Historie":
        zobrazit_historii_uctu()
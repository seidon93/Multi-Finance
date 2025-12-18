import sys
import os
from datetime import date, timedelta
import streamlit as st
import pandas as pd
from decimal import Decimal
import time

# Zajištění, že se importují moduly z nadřazeného adresáře (core)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, os.pardir))

from dotenv import load_dotenv

# --- DŮLEŽITÉ: POUŽÍVÁ SE POUZE SKUTEČNÁ LOGIKA Z DATABÁZE ---
try:
    from core.accounting_logic import AccountingEngine
except ImportError:
    st.error("Chyba importu: Modul 'core.accounting_logic.AccountingEngine' nebyl nalezen.")
    st.stop()  # Zastaví aplikaci, pokud nelze načíst klíčový modul

load_dotenv()
DB_PASSWORD = os.environ.get("DB_PASSWORD")

KLIENT_ID = 1
if 'metoda_zasob' not in st.session_state:
    st.session_state.metoda_zasob = 'B'


# Inicializace účetního enginu (globálně)
engine = AccountingEngine(klient_id=KLIENT_ID)
metoda_zasob = st.session_state.metoda_zasob

# --- KOMPLETNÍ CSS STYLING ---
st.markdown(
    """
    <style>
    /* 1. GLOBÁLNÍ ÚPRAVA HLAVNÍHO KONTEJNERU */
    /* Vynutí, aby veškerý obsah začínal u levého okraje menu a posouval se s ním */
    [data-testid="stAppViewBlockContainer"] {
        padding-left: 2rem !important; 
        padding-right: 2rem !important;
        padding-top: 2rem !important;
        max-width: 95% !important;
    }

    /* 2. HLAVNÍ NADPIS V LEVÉM ROHU */
    .main-header-container {
        text-align: left;
        margin-top: -105px; /* Vytáhne nadpis nad vodorovný proužek do lišty */
        margin-bottom: 25px;
        width: 100%;
        display: block;
    }

    .main-header-title {
        font-size: 2.2rem !important;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -1px;
        margin-left: 0 !important;
    }

    /* Skrytí standardní průhledné lišty Streamlitu */
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
        border-bottom: none !important;
    }

    /* 3. SIDEBAR: VERTIKÁLNÍ TLAČÍTKA A MEZERY */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }

    /* Vizuální úprava oddělovače v sidebaru */
    [data-testid="stSidebar"] hr {
        margin-top: 0.8rem !important;
        margin-bottom: 0.8rem !important;
        border-top: 1px solid #444;
    }

    /* Menší nadpisy v sidebaru */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h3 {
        font-size: 1.3rem !important;
        margin-bottom: 5px !important;
    }

    /* 4. FORMULÁŘ: RÁMEČEK A SYMETRIE */
    /* Vylepšení vzhledu st.container(border=True) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #121212; 
        border-radius: 12px;
        padding: 30px;
        border: 1px solid #333 !important;
    }

    /* Mezera mezi sloupci MD a DAL */
    [data-testid="stHorizontalBlock"] {
        gap: 3rem !important;
    }

    /* 5. OSTATNÍ FUNKČNÍ STYLY */
    [data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 200px;
    }

    .zustatek-kladny { color: #28a745 !important; font-size: 1.15em !important; font-weight: bold !important; }
    .zustatek-zaporny { color: #dc3545 !important; font-size: 1.15em !important; font-weight: bold !important; }

    .ucet-nazev {
        color: #007bff !important;
        font-size: 1.25em !important; 
        font-weight: bold !important;
    }

    /* Tlačítko Uložit - Červené a výrazné */
    div.stButton > button[kind="primary"] {
        background-color: #A93226 !important;
        color: white !important;
        border: 1px solid #A93226 !important;
        border-radius: 6px;
        font-weight: 600;
        height: 3rem;
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover { 
        background-color: #C0392B !important; 
        border-color: #C0392B !important;
        transform: translateY(-1px);
    }

    /* Oranžové efekty (pro speciální tlačítka) */
    .orange-hover-container button { 
        border-color: #ff9800 !important; 
        color: #ff9800 !important; 
    }
    .orange-hover-container button:hover {
        background-color: rgba(255, 152, 0, 0.1) !important;
    }

    /* Responzivita pro mobilní telefony */
    @media (max-width: 768px) {
        [data-testid="stAppViewBlockContainer"] { padding-left: 1rem !important; padding-right: 1rem !important; }
        .main-header-container { margin-top: 0; text-align: center; }
        .main-header-title { font-size: 1.6rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True
)
import time


def uloz_transakci_ui():
    # ... načtení hodnot z formuláře ...
    doklad = st.text_input("Číslo dokladu")

    if st.button("Uložit"):
        # Kontrola unikátnosti dokladu
        check = execute_query("SELECT 1 FROM Transakce WHERE doklad_cislo = ?", (doklad,))
        if check:
            doklad = f"{doklad}-{int(time.time())}"  # Přidá timestamp pro unikátnost
            st.warning(f"Doklad s tímto číslem již existoval. Uloženo jako: {doklad}")


# --- POMOCNÁ FUNKCE PRO PŘEVOD MĚNY (VLOŽIT NA ZAČÁTEK SOUBORU) ---
def parse_input_money(text_value):
    """
    Převede textový vstup (např. '1.5m', '100k', '50 000') na float.
    """
    if not text_value:
        return 0.0

    # Odstraníme mezery a převedeme na malé písmo
    # Nahradíme čárku tečkou pro float konverzi
    clean_val = str(text_value).replace(" ", "").replace(",", ".").lower().strip()

    try:
        if clean_val.endswith('k'):
            return float(clean_val[:-1]) * 1_000
        elif clean_val.endswith('m'):
            return float(clean_val[:-1]) * 1_000_000
        else:
            return float(clean_val)
    except ValueError:
        return 0.0


def zobrazit_header():
    """Vytvoří hlavičku v levém rohu a navigační menu."""

    st.markdown("""
        <div class="main-header-container">
            <h1 class="main-header-title">💰 Multi-Finance Účetní Systém</h1>
        </div>
    """, unsafe_allow_html=True)

    # --- Nastavení v sidebaru ---
    st.sidebar.markdown("## ⚙️ Nastavení systému  ")

    # Změněno na vertikální zobrazení pro zásoby
    st.session_state.metoda_zasob = st.sidebar.radio(
        "Metoda účtování zásob:",
        ('A', 'B'),
        index=1 if st.session_state.metoda_zasob == 'B' else 0,
        help="A = Průběžně (111), B = Přímo (501)",
        horizontal=True  # Zajišťuje vertikální rozložení tlačítek
    )

    st.sidebar.markdown("---")

    # --- Navigace ---
    st.sidebar.markdown("## 🗺️ Navigace")
    vyber = st.sidebar.radio(
        "Zvolte Modul:",
        ("Nová Transakce", "Přehled Účtů", "Přehled DPH", "Historie", "Reporty", "Uzávěrka"),
        label_visibility="collapsed"
    )
    return vyber


def formular_nova_transakce():
    # HLAVNÍ KONTEJNER S BORDEREM
    with st.container(border=True):
        st.header("Vytvořit Novou Transakci")

        # --- 1. HLAVIČKA DOKLADU ---
        c1, c2 = st.columns(2)
        default_doklad = f"FP-{KLIENT_ID}-{date.today().strftime('%Y%m%d')}"
        doklad_cislo = c1.text_input("Číslo Dokladu", value=default_doklad)
        datum_transakce = c2.date_input("Datum Transakce", value=date.today())
        popis = st.text_area("Popis", placeholder="Popis účetní operace...")

        st.markdown("---")
        manualni_rezim = st.checkbox("✍️ Zadat účty ručně pro vlastní analytiku", value=False)

        c_md, c_dal = st.columns(2)

        # --- LOGIKA PRO MD ---
        with c_md:
            st.subheader("MD (Má Dáti)")
            if manualni_rezim:
                ucet_md_zaklad = st.text_input("Číslo účtu MD", placeholder="např. 518.001", key="md_man")
            else:
                tridy_uctu = ["0 - Dlouhodobý majetek", "1 - Zásoby", "2 - Krát. fin. majetek", "3 - Zúčtovací vztahy",
                              "4 - Kapitálové účty", "5 - Náklady", "6 - Výnosy"]
                trida_md_sel = st.selectbox("Třída", tridy_uctu, key="t_md")
                prefix_md = trida_md_sel.split(" - ")[0]
                zakladni_ucty_md = engine.get_zakladni_ucty_podle_tridy(prefix_md)
                vyber_zaklad_md = st.selectbox("Základní účet", zakladni_ucty_md, key="u_md_base")

                if vyber_zaklad_md:
                    cislo_zaklad_md = vyber_zaklad_md.split(" - ")[0]
                    analytika_md = engine.get_analytika_pro_ucet(cislo_zaklad_md)
                    if analytika_md:
                        vyber_analytika_md = st.selectbox("↳ Analytický podúčet", analytika_md, key="u_md_anal")
                        ucet_md_zaklad = vyber_analytika_md.split(" - ")[0]
                    else:
                        ucet_md_zaklad = cislo_zaklad_md
                else:
                    ucet_md_zaklad = None

        # --- LOGIKA PRO DAL ---
        with c_dal:
            st.subheader("D (Dal)")
            if manualni_rezim:
                ucet_dal_zaklad = st.text_input("Číslo účtu D", placeholder="např. 321", key="dal_man")
            else:
                trida_d_sel = st.selectbox("Třída", tridy_uctu, index=2, key="t_d")
                prefix_d = trida_d_sel.split(" - ")[0]
                zakladni_ucty_d = engine.get_zakladni_ucty_podle_tridy(prefix_d)
                vyber_zaklad_d = st.selectbox("Základní účet", zakladni_ucty_d, key="u_d_base")

                if vyber_zaklad_d:
                    cislo_zaklad_d = vyber_zaklad_d.split(" - ")[0]
                    analytika_d = engine.get_analytika_pro_ucet(cislo_zaklad_d)
                    if analytika_d:
                        vyber_analytika_d = st.selectbox("↳ Analytický podúčet", analytika_d, key="u_d_anal")
                        ucet_dal_zaklad = vyber_analytika_d.split(" - ")[0]
                    else:
                        ucet_dal_zaklad = cislo_zaklad_d
                else:
                    ucet_dal_zaklad = None

        # --- ČÁSTKA A ZBYTEK ---
        st.markdown("---")
        col_castka, col_prev = st.columns(2)
        raw_castka = col_castka.text_input("Částka bez DPH", placeholder="1.2m, 50k", key="money_in")
        castka_bez_dph = parse_input_money(raw_castka)
        if castka_bez_dph > 0:
            col_prev.metric("K zaúčtování", f"{castka_bez_dph:,.2f} Kč".replace(",", " "))

        c_dph1, c_dph2 = st.columns(2)
        dph_opts = sorted(list(engine.get_dph_sazby().keys()), reverse=True)
        vybrana_sazba = c_dph1.selectbox("DPH %", dph_opts, index=dph_opts.index(0.0) if 0.0 in dph_opts else 0)
        smer_dph = c_dph2.radio("Typ DPH", ['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'], horizontal=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Uložit Transakci", type="primary", use_container_width=True):
            # ... logika uložení (beze změny) ...
            pass


def time_filter_ui():
    """Vykreslí tlačítka a výběr rozmezí včetně ČTVRTLETÍ."""

    st.subheader("Filtrování časového rozmezí")

    dnes = date.today()
    aktualni_rok = dnes.year

    # Uložení stavu vybraných dat do session state
    if 'filter_date_from' not in st.session_state:
        st.session_state['filter_date_from'] = None
    if 'filter_date_to' not in st.session_state:
        st.session_state['filter_date_to'] = None

    # --- Pomocná funkce pro nastavení a reload ---
    def set_dates(d_from, d_to):
        st.session_state['filter_date_from'] = d_from
        st.session_state['filter_date_to'] = d_to
        st.rerun()

    # --- Pomocné výpočty dat ---
    def get_start_of_week(d):
        return d - timedelta(days=d.weekday())

    def get_start_of_month(d):
        return d.replace(day=1)

    # Funkce pro konec měsíce
    def get_end_of_month(d):
        # První den dalšího měsíce - 1 den
        next_month = d.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    def get_start_of_year(d):
        return d.replace(month=1, day=1)

    def get_end_of_year(d):
        return d.replace(month=12, day=31)

    # --- KONTEJNER PRO FILTRY ---
    with st.container(border=True):

        # Řádek 1: Základní rychlá volba
        c1, c2, c3, c4 = st.columns(4)

        if c1.button("Dnes", width="stretch"):
            set_dates(dnes, dnes)

        if c2.button("Tento týden", width="stretch"):
            start_week = get_start_of_week(dnes)
            end_week = start_week + timedelta(days=6)
            set_dates(start_week, end_week)

        if c3.button("Tento měsíc", width="stretch"):
            start_month = get_start_of_month(dnes)
            end_month = get_end_of_month(dnes)
            set_dates(start_month, end_month)

        if c4.button("Tento rok", width="stretch"):
            set_dates(get_start_of_year(dnes), get_end_of_year(dnes))

        # --- NOVÉ: Řádek 2: Čtvrtletí ---
        q1, q2, q3, q4 = st.columns(4)

        # 1. Čtvrtletí (leden - březen)
        if q1.button("1. Čtvrtletí (Q1)", width="stretch"):
            set_dates(date(aktualni_rok, 1, 1), date(aktualni_rok, 3, 31))

        # 2. Čtvrtletí (duben - červen)
        if q2.button("2. Čtvrtletí (Q2)", width="stretch"):
            set_dates(date(aktualni_rok, 4, 1), date(aktualni_rok, 6, 30))

        # 3. Čtvrtletí (červenec - září)
        if q3.button("3. Čtvrtletí (Q3)", width="stretch"):
            set_dates(date(aktualni_rok, 7, 1), date(aktualni_rok, 9, 30))

        # 4. Čtvrtletí (říjen - prosinec)
        if q4.button("4. Čtvrtletí (Q4)", width="stretch"):
            set_dates(date(aktualni_rok, 10, 1), date(aktualni_rok, 12, 31))

        # Řádek 3: Ruční výběr a Reset
        col_from, col_to, col_reset = st.columns([1.2, 1.2, 0.7], vertical_alignment="bottom")

        new_date_from = col_from.date_input(
            "Datum OD",
            value=st.session_state['filter_date_from'],
            key='picker_from'
        )

        new_date_to = col_to.date_input(
            "Datum DO",
            value=st.session_state['filter_date_to'],
            key='picker_to'
        )

        if col_reset.button("Reset filtrů", type="primary", width="stretch"):
            set_dates(None, None)

        # Logika aktualizace při ruční změně
        if new_date_from != st.session_state['filter_date_from'] or new_date_to != st.session_state['filter_date_to']:
            st.session_state['filter_date_from'] = new_date_from
            st.session_state['filter_date_to'] = new_date_to
            st.rerun()

        return st.session_state['filter_date_from'], st.session_state['filter_date_to']


def zobrazit_reporty():
    st.header("📊 Účetní závěrka (Financial Reports)")

    # --- FILTR ---
    date_from, date_to = time_filter_ui()

    # Načtení dat
    data = engine.get_report_data(date_from, date_to)

    if date_from and date_to:
        st.caption(f"Období: {date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}")
    else:
        st.caption("Období: Kumulativně od počátku")

    st.markdown("---")

    # --- ZÁLOŽKY ---
    tab_vysledovka, tab_rozvaha = st.tabs(["📉 Výsledovka", "⚖️ Rozvaha"])

    # =========================================================
    # 1. VÝSLEDOVKA (BANNER + VERTIKÁLNÍ TABULKY)
    # =========================================================
    with tab_vysledovka:
        hv = data['hospodarsky_vysledek']
        barva_hv = "#28a745" if hv >= 0 else "#dc3545"
        bg_hv = "rgba(40, 167, 69, 0.1)" if hv >= 0 else "rgba(220, 53, 69, 0.1)"
        label_hv = "ČISTÝ ZISK" if hv >= 0 else "ZTRÁTA"

        # BANNER VÝSLEDKU
        st.markdown(
            f"""
            <div style="background-color: {bg_hv}; padding: 15px; border-radius: 8px; border-left: 5px solid {barva_hv}; text-align: center; margin-bottom: 30px;">
                <h4 style="margin:0; color: #888;">VÝSLEDEK HOSPODAŘENÍ ({label_hv})</h4>
                <h1 style="margin:0; color: {barva_hv}; font-size: 2.2em;"> 💵 {hv:,.2f} Kč</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- NÁKLADY ---
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #dc3545; padding-bottom: 5px; margin-bottom: 10px;'>Náklady</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #dc3545; margin-top: 0px;'>{data['suma_naklady']:,.2f} Kč</h1>",
                    unsafe_allow_html=True)

        if data['naklady']:
            df = pd.DataFrame(data['naklady'])
            df['castka'] = df['castka'].apply(lambda x: f"{x:,.2f}")
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            df = df[['Účet', 'Název', 'Částka']]
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.info("Žádné náklady.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- VÝNOSY ---
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #28a745; padding-bottom: 5px; margin-bottom: 10px;'>Výnosy</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #28a745; margin-top: 0px;'>{data['suma_vynosy']:,.2f} Kč</h1>",
                    unsafe_allow_html=True)

        if data['vynosy']:
            df = pd.DataFrame(data['vynosy'])
            df['castka'] = df['castka'].apply(lambda x: f"{x:,.2f}")
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            df = df[['Účet', 'Název', 'Částka']]
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.info("Žádné výnosy.")

    # =========================================================
    # 2. ROZVAHA (BANNER SHODY + VERTIKÁLNÍ TABULKY)
    # =========================================================
    with tab_rozvaha:
        rozdil = data['suma_aktiva'] - data['suma_pasiva']
        bilance_ok = abs(rozdil) < 0.02

        # --- LOGIKA BAREV A TEXTU PRO BANNER ---
        if bilance_ok:
            # Zelený styl (Vše OK)
            barva_ban = "#28a745"
            bg_ban = "rgba(40, 167, 69, 0.1)"
            nadpis_ban = "STAV BILANCE"
            text_ban = "✅ BILANCE JE VYROVNANÁ"
        else:
            # Červený styl (Chyba)
            barva_ban = "#dc3545"
            bg_ban = "rgba(220, 53, 69, 0.1)"
            nadpis_ban = "⚠️ NESHODA V BILANCI"
            text_ban = f"ROZDÍL: {rozdil:,.2f} Kč"

        # --- HTML BANNER PRO BILANCI ---
        st.markdown(
            f"""
            <div style="background-color: {bg_ban}; padding: 15px; border-radius: 8px; border-left: 5px solid {barva_ban}; text-align: center; margin-bottom: 30px;">
                <h4 style="margin:0; color: #888;">{nadpis_ban}</h4>
                <h1 style="margin:0; color: {barva_ban}; font-size: 2.2em;">{text_ban}</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # -----------------------------------------------------
        # SEKCE 1: AKTIVA (Modrá)
        # -----------------------------------------------------
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #007bff; padding-bottom: 5px; margin-bottom: 10px;'>Aktiva (Majetek)</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #007bff; margin-top: 0px;'>{data['suma_aktiva']:,.2f} Kč</h1>",
                    unsafe_allow_html=True)

        if data['aktiva']:
            df = pd.DataFrame(data['aktiva'])
            df['castka'] = df['castka'].apply(lambda x: f"{x:,.2f}")
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            df_final = df[['Účet', 'Název', 'Částka']]

            st.dataframe(
                df_final,
                hide_index=True,
                width="stretch",
                column_config={
                    "Účet": st.column_config.TextColumn("Účet", width="small"),
                    "Název": st.column_config.TextColumn("Název", width="medium"),
                    "Částka": st.column_config.TextColumn("Částka", width="small"),
                }
            )
        else:
            st.info("Žádná aktiva.")

        st.markdown("<br>", unsafe_allow_html=True)

        # -----------------------------------------------------
        # SEKCE 2: PASIVA (Žlutá)
        # -----------------------------------------------------
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #ffc107; padding-bottom: 5px; margin-bottom: 10px;'>Pasiva (Zdroje)</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #ffc107; margin-top: 0px;'>{data['suma_pasiva']:,.2f} Kč</h1>",
                    unsafe_allow_html=True)

        if data['pasiva']:
            df = pd.DataFrame(data['pasiva'])

            # FILTR: Odstranění HV z tabulky Pasiv
            df = df[df['ucet'] != 'HV']

            if not df.empty:
                df['castka'] = df['castka'].apply(lambda x: f"{x:,.2f}")
                df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
                df_final = df[['Účet', 'Název', 'Částka']]

                st.dataframe(
                    df_final,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Účet": st.column_config.TextColumn("Účet", width="small"),
                        "Název": st.column_config.TextColumn("Název", width="medium"),
                        "Částka": st.column_config.TextColumn("Částka", width="small"),
                    }
                )
            else:
                st.caption("Žádná pasiva (kromě HV).")
        else:
            st.caption("Žádná pasiva.")


def zobrazit_prehled_uctu():
    # --- TOTÁLNÍ CSS PRO CENTROVÁNÍ ---
    st.markdown("""
        <style>
            /* 1. Kontejner pro text - vynucení středu */
            .analytika-text-wrapper {
                width: 100%;
                text-align: center;
                margin-top: 30px;
                margin-bottom: 10px;
            }
            .analytika-text-wrapper span {
                font-weight: bold;
                font-size: 1.25rem !important;
                color: white;
                display: inline-block;
            }

            /* 2. Cílení přímo na kontejner widgetu Streamlit */
            div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stCheckbox"]) {
                display: flex !important;
                justify-content: center !important;
                width: 100% !important;
            }

            /* 3. Vystředění samotného toggle a jeho zvětšení */
            div[data-testid="stCheckbox"] {
                display: flex !important;
                justify-content: center !important;
                width: auto !important;
                margin: 0 auto !important;
                zoom: 1.7; /* Ještě o něco větší pro lepší viditelnost */
            }

            /* 4. Skrytí labelu, aby nezabíral místo vpravo */
            div[data-testid="stCheckbox"] label {
                margin: 0 !important;
                padding: 0 !important;
            }
            div[data-testid="stCheckbox"] div[data-testid="stWidgetLabel"] {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # 1. NADPIS
    st.header("📊 Hlavní Přehled Účtů")

    # 2. FILTRY (Standardní zobrazení)
    d_od, d_do = time_filter_ui()

    # --- TATO ČÁST MUSÍ BÝT VOLNĚ V KÓDU (Mimo columns!) ---

    # Textový nadpis na středu
    st.markdown('<div class="analytika-text-wrapper"><span>Analytika v detailech</span></div>', unsafe_allow_html=True)

    # Přepínač na středu
    is_detail = st.toggle("", value=False, label_visibility="collapsed", key="toggle_FINAL_CENTER")

    # 3. NAČTENÍ A VÝPIS DAT
    data = engine.get_report_data(d_od, d_do, detailni=is_detail)

    if data:
        vsechny = data.get('aktiva', []) + data.get('pasiva', []) + \
                  data.get('naklady', []) + data.get('vynosy', [])

        if vsechny:
            df = pd.DataFrame(vsechny)
            df.columns = ['Účet', 'Název', 'Zůstatek']
            df['Zůstatek'] = df['Zůstatek'].apply(lambda x: f"{x:,.2f} Kč".replace(",", " ").replace(".", ","))

            st.dataframe(df, width="stretch", hide_index=True)

            hv = data.get('hospodarsky_vysledek', 0.0)
            st.metric("Průběžný Hospodářský Výsledek (HV)", f"{hv:,.2f} Kč".replace(",", " ").replace(".", ","))


def zobrazit_prehled_dph():
    st.header("Daňová Povinnost DPH")

    # 1. Získání časového filtru
    date_from, date_to = time_filter_ui()
    st.markdown("---")

    # 2. Výpočet dat
    try:
        dph_data_raw = engine.spocti_prehled_dph(datum_od=date_from, datum_do=date_to)
        # Bezpečné vyjmutí celkové sumy
        celkem = dph_data_raw.pop('CELKEM', Decimal('0.0'))
    except Exception as e:
        st.error(f"Chyba při výpočtu DPH: {e}")
        dph_data_raw = {}
        celkem = Decimal('0.0')

    # --- DEBUG: Ověření pro vás (pokud vidíte 0, filtr funguje) ---
    # Pokud zadáte rok 2020 a je tu 0, ale v "Tento rok" je číslo, vše funguje.
    # st.caption(f"DEBUG: Aplikovaný filtr: {date_from} až {date_to}. Celkem nalezeno: {celkem}")

    # 3. Informační hlavička
    date_from_str = date_from.strftime('%d.%m.%Y') if date_from else 'Počátek'
    date_to_str = date_to.strftime('%d.%m.%Y') if date_to else 'Současnost'

    st.info(f"Přehled DPH za období: **{date_from_str} – {date_to_str}**")

    # 4. Tabulka detailů
    st.subheader("Detailní Přehled po Sazbách")

    if not dph_data_raw:
        st.warning("V tomto období nejsou žádné pohyby DPH.")
    else:
        detail_data = []
        dph_ucty_map = engine.get_dph_sazby()
        sorted_sazby = sorted([k for k in dph_data_raw.keys()], reverse=True)

        for sazba in sorted_sazby:
            data = dph_data_raw[sazba]
            ucty_map = dph_ucty_map.get(sazba, {'vstup': '?', 'vystup': '?'})

            vstup = data.get('vstup', Decimal('0.0'))
            vystup = data.get('vystup', Decimal('0.0'))
            rozdil = data.get('rozdil', Decimal('0.0'))

            # ZDE BYLA CHYBA: Názvy sloupců musí být statické, účty dáme do závorky hodnoty nebo zvlášť
            detail_data.append({
                'Sazba': f"{sazba:.0f} %",
                'DPH Vstup (MD)': f"{vstup:,.2f} Kč".replace(",", " ").replace(".", ","),
                'DPH Výstup (D)': f"{vystup:,.2f} Kč".replace(",", " ").replace(".", ","),
                'Rozdíl': f"{rozdil:,.2f} Kč".replace(",", " ").replace(".", ","),
                # Skryté info o účtech pro tooltip nebo kontrolu (volitelné)
                'Účty': f"Vstup: {ucty_map['vstup']} | Výstup: {ucty_map['vystup']}"
            })

        if detail_data:
            df_detail = pd.DataFrame(detail_data)
            st.dataframe(
                df_detail,
                hide_index=True,
                width="stretch",
                column_config={
                    "Účty": st.column_config.TextColumn("Použité účty", help="Účty použité pro výpočet")
                }
            )

    # 5. Celková povinnost (Barevný Box)
    st.subheader("Celková Daňová Povinnost")

    # Logika barev a textů
    if celkem > Decimal('0.005'):
        typ = "NEDOPLATEK (K ÚHRADĚ)"
        barva_css = "#dc3545"  # Červená
        # Nedoplatek je kladný, zobrazujeme tak jak je
        suma_str = f"{celkem:,.2f} Kč"
    elif celkem < Decimal('-0.005'):
        typ = "PŘEPLATEK (K VRÁCENÍ)"
        barva_css = "#28a745"  # Zelená
        # Přeplatek je záporný, ale chceme zobrazit kladné číslo "Kolik nám vrátí"
        suma_str = f"{abs(celkem):,.2f} Kč"
    else:
        typ = "NULOVÁ POVINNOST"
        barva_css = "#007bff"  # Modrá
        suma_str = "0,00 Kč"

    suma_str = suma_str.replace(",", " ").replace(".", ",")

    st.markdown(
        f"""
        <div class='dph-box' style='border-color: {barva_css}; color: {barva_css};'>
            <h4 style='color: inherit; margin: 0;'>{typ}</h4>
            <h1 style='color: inherit; margin: 10px 0;'>{suma_str}</h1>
        </div>
        """,
        unsafe_allow_html=True
    )


def zobrazit_historii_uctu():
    st.header("Historie a Editace Transakcí")

    # --- 1. SEKCE FILTRŮ ---
    st.subheader("🔍 Vyhledat transakce")

    metoda = st.radio(
        "Podle čeho chcete hledat?",
        ["📅 Podle data transakce", "📄 Podle čísla dokladu (Faktury)", "👤 Podle Klienta (ID)"],
        horizontal=True
    )

    sql_base = """
        SELECT T.id, T.datum, T.doklad_cislo, T.popis, SUM(P.castka) as Objem
        FROM Transakce T
        JOIN UcetniPohyby P ON T.id = P.transakce_id
        WHERE 1=1
    """
    params = []

    # --- LOGIKA FILTRŮ ---
    if metoda == "📅 Podle data transakce":
        date_from, date_to = time_filter_ui()
        if not date_from or not date_to:
            st.info("Zvolte prosím časové období.")
            return
        sql_base += " AND T.klient_id = ? AND T.datum >= ? AND T.datum <= ?"
        params = [KLIENT_ID, date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')]

    elif metoda == "📄 Podle čísla dokladu (Faktury)":
        col_search, _ = st.columns([2, 1])
        hledany_text = col_search.text_input("Zadejte číslo dokladu (nebo jeho část):", placeholder="např. FP-2025")
        sql_base += " AND T.klient_id = ? AND T.doklad_cislo LIKE ?"
        params = [KLIENT_ID, f"%{hledany_text}%"]
        if not hledany_text:
            st.info("Zadejte alespoň jeden znak pro vyhledání.")
            return

    elif metoda == "👤 Podle Klienta (ID)":
        st.caption(f"Aktuálně přihlášený klient ID: {KLIENT_ID}")
        sql_base += " AND T.klient_id = ?"
        params = [KLIENT_ID]

    sql_base += " GROUP BY T.id, T.datum, T.doklad_cislo, T.popis ORDER BY T.datum DESC, T.id DESC"

    # --- 2. VYKONÁNÍ DOTAZU ---
    from core.database import execute_query
    try:
        rows = execute_query(sql_base, tuple(params))
    except Exception as e:
        st.error(f"Chyba při vyhledávání: {e}")
        return

    if not rows:
        st.warning("⚠️ Žádné transakce nebyly nalezeny.")
        return

    # Převedeme na tuple pro Pandas
    rows_clean = [tuple(r) for r in rows]

    # --- 3. VÝPIS DAT (ROZTAŽENÁ TABULKA) ---
    st.success(f"Nalezeno {len(rows_clean)} záznamů.")

    df = pd.DataFrame(rows_clean, columns=["ID", "Datum", "Doklad", "Popis", "Objem (pohyby)"])
    if not df.empty:
        df['Datum'] = pd.to_datetime(df['Datum']).dt.date
        df['Objem (pohyby)'] = df['Objem (pohyby)'].apply(lambda x: f"{x:,.2f} Kč")

    # === ZDE JE ZMĚNA PRO ROZTAŽENÍ ===
    st.dataframe(
        df,
        width="stretch",  # Roztáhne kontejner
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Datum": st.column_config.DateColumn("Datum", width="small"),
            "Doklad": st.column_config.TextColumn("Doklad", width="small"),
            # Popis nastavíme na "large", aby se roztáhl a vyplnil zbytek místa
            "Popis": st.column_config.TextColumn("Popis", width="large"),
            "Objem (pohyby)": st.column_config.TextColumn("Objem", width="medium"),
        }
    )

    # --- 4. SEKCE EDITACE ---
    st.subheader("✏️ Upravit vybranou transakci")

    moznosti = [f"{r[2]} | {r[1]} | {r[3]} (ID: {r[0]})" for r in rows_clean]
    vybrana_str = st.selectbox("Vyberte ze seznamu výše:", moznosti)

    if vybrana_str:
        import re
        match = re.search(r"\(ID: (\d+)\)", vybrana_str)
        if match:
            transakce_id = int(match.group(1))

            detail = engine.get_transakce_detail(transakce_id)

            if detail:
                with st.form(key=f"edit_form_{transakce_id}"):
                    st.markdown(f"**Editujete doklad:** `{detail['doklad']}` ze dne `{detail['datum']}`")

                    c1, c2 = st.columns(2)
                    new_doklad = c1.text_input("Doklad", value=detail['doklad'])
                    new_datum = c2.date_input("Datum", value=detail['datum'])
                    new_popis = st.text_area("Popis", value=detail['popis'])

                    st.markdown("---")
                    st.markdown("**Účetní data (Zadejte novou správnou kontaci):**")

                    tridy_uctu = ["0 - Dlouhodobý majetek", "1 - Zásoby", "2 - Finanční účty", "3 - Zúčtovací vztahy",
                                  "4 - Kapitálové účty", "5 - Náklady", "6 - Výnosy"]

                    ce1, ce2 = st.columns(2)
                    with ce1:
                        md_trida = st.selectbox("Třída MD", tridy_uctu, key=f"e_md_t_{transakce_id}")
                        ucty_md = engine.get_ucty_podle_tridy(md_trida.split(" - ")[0])
                        sel_md = st.selectbox("Účet MD", ucty_md, key=f"e_md_u_{transakce_id}")
                        ucet_md_fin = sel_md.split(" - ")[0] if sel_md else ""

                    with ce2:
                        d_trida = st.selectbox("Třída D", tridy_uctu, index=2, key=f"e_d_t_{transakce_id}")
                        ucty_d = engine.get_ucty_podle_tridy(d_trida.split(" - ")[0])
                        sel_d = st.selectbox("Účet D", ucty_d, key=f"e_d_u_{transakce_id}")
                        ucet_dal_fin = sel_d.split(" - ")[0] if sel_d else ""

                    # Odhad částky
                    odhad = 0.0
                    if detail['pohyby']:
                        odhad = max([p['castka'] for p in detail['pohyby']])

                    c_money, c_dph = st.columns(2)

                    # Text input pro podporu zkratek (10m, 5k)
                    odhad_str = f"{odhad:.2f}" if odhad else ""
                    new_castka_raw = c_money.text_input(
                        "Částka základu (bez DPH)",
                        value=odhad_str,
                        help="Můžete zadávat zkratky: 10m = 10 milionů, 5k = 5 tisíc."
                    )

                    dph_sazby = engine.get_dph_sazby()
                    dph_opts = sorted(list(dph_sazby.keys()), reverse=True)
                    new_sazba = c_dph.selectbox("Sazba DPH", dph_opts, key=f"e_dph_s_{transakce_id}")
                    new_smer_dph = c_dph.radio("Typ DPH", ['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'],
                                               key=f"e_dph_r_{transakce_id}")

                    st.markdown("")
                    save_btn = st.form_submit_button("💾 Uložit opravu", type="primary")

                    if save_btn:
                        final_castka = parse_input_money(new_castka_raw)

                        if final_castka <= 0:
                            st.error("Částka musí být větší než 0.")
                        else:
                            try:
                                engine.upravit_transakci(
                                    transakce_id=transakce_id,
                                    nove_datum=new_datum,
                                    novy_popis=new_popis,
                                    novy_doklad=new_doklad,
                                    ucet_md=ucet_md_fin,
                                    ucet_dal=ucet_dal_fin,
                                    castka=final_castka,
                                    sazba_dph=new_sazba,
                                    smer_dph_popis=new_smer_dph
                                )
                                st.success(f"✅ Změna uložena! (Nová částka: {final_castka:,.2f} Kč)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Chyba: {e}")


def zobrazit_uzaverku():
    st.header("🔒 Správa Účetních Období & Roční Závěrka")

    aktualni_uzaverka = engine.get_datum_uzaverky()
    dnes = date.today()

    # --- STATUS BAR ---
    if aktualni_uzaverka:
        st.warning(f"⛔ Účetnictví je UZAMČENO k datu: **{aktualni_uzaverka.strftime('%d. %m. %Y')}**")
    else:
        st.success("✅ Účetnictví je OTEVŘENÉ.")

    st.markdown("---")

    tabs = st.tabs([
        "🧮 Daň z příjmů (Kalkulace)",
        "🔚 Roční závěrka (702)",
        "🆕 Otevření roku (701)",
        "🔒 Uzamykání data"
    ])

    # =========================================================
    # TAB 1: KALKULACE DANĚ
    # =========================================================
    with tabs[0]:
        st.subheader("Výpočet daně z příjmů právnických osob (DPPO)")

        # 1. Výběr roku
        col_rok, _ = st.columns([1, 3])
        vybrany_rok = col_rok.number_input("Zvolte rok", value=dnes.year, step=1)

        # 2. Načtení dat a výpočet EBT (Zisk před zdaněním)
        d_od = date(vybrany_rok, 1, 1)
        d_do = date(vybrany_rok, 12, 31)
        report_data = engine.get_report_data(d_od, d_do)

        hv_ucetni = report_data.get('hospodarsky_vysledek', 0.0)

        # Aby se nám zisk neměnil pod rukama po zaúčtování daně,
        # musíme k němu přičíst zpět náklady na účtech 59x (pokud už tam nějaké jsou).
        naklady_dan = sum(pol['castka'] for pol in report_data['naklady'] if str(pol['ucet']).startswith('59'))

        # HRUBÝ ZISK (EBT) = Účetní HV + Náklady na daň
        hruby_zisk_ebt = hv_ucetni + naklady_dan

        # --- BANNER PRO HRUBÝ ZISK ---
        if hruby_zisk_ebt >= 0:
            barva_text = "#28a745"  # Zelená
            barva_bg = "rgba(40, 167, 69, 0.15)"
            popisek = "Hrubý zisk (před zdaněním)"
            ikona = "📈"
        else:
            barva_text = "#dc3545"  # Červená
            barva_bg = "rgba(220, 53, 69, 0.15)"
            popisek = "Hrubá ztráta (před zdaněním)"
            ikona = "📉"

        st.markdown(f"""
            <div style="background-color: {barva_bg}; padding: 15px; border-radius: 10px; border: 2px solid {barva_text}; text-align: center; margin-bottom: 25px;">
                <h4 style="margin:0; color: {barva_text}; opacity: 0.9;">{ikona} {popisek}</h4>
                <h1 style="margin:0; color: {barva_text}; font-size: 3em; font-weight: bold;">{hruby_zisk_ebt:,.2f} Kč</h1>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### Stanovení daňové povinnosti")

        # 3. Formulář
        c1, c_space, c2 = st.columns([2, 0.2, 1])

        # A) Základ daně (Defaultně EBT, ale lze změnit)
        default_zaklad = max(0.0, hruby_zisk_ebt)

        with c1:
            zaklad_dane = st.number_input("Základ daně (Kč)", value=default_zaklad, step=1000.0,
                                          help="Upravený základ daně.")

        # B) Sazba (vpravo)
        with c2:
            sazba_dane = st.number_input("Sazba daně (%)", value=21.0, step=1.0, format="%.1f")

        # 4. Výpočet
        vypoctena_dan = zaklad_dane * (sazba_dane / 100.0)

        # 5. VÝSLEDEK (Barevně rozlišený)
        st.markdown("<br>", unsafe_allow_html=True)

        if vypoctena_dan > 0:
            res_color = "#dc3545"  # Červená
            res_bg = "rgba(220, 53, 69, 0.1)"
            res_text = "SPLATNÉ (K ÚHRADĚ)"
        else:
            res_color = "#28a745"  # Zelená
            res_bg = "rgba(40, 167, 69, 0.1)"
            res_text = "BEZ POVINNOSTI"

        st.markdown(f"""
            <div style="text-align: center; background-color: {res_bg}; padding: 10px 15px; border-radius: 8px; border: 1px solid {res_color}; margin-bottom: 20px;">
                <h5 style="margin:0; color: #888; font-weight: normal;">Daňová povinnost k úhradě</h5>
                <h1 style="margin: 5px 0; color: {res_color}; font-size: 2.4em;">{vypoctena_dan:,.2f} Kč</h1>
                <div style="color: {res_color}; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; font-size: 0.9em;">{res_text}</div>
            </div>
        """, unsafe_allow_html=True)

        # 6. Tlačítko
        if st.button("📝 Zaúčtovat daň (591 / 341)", type="primary", width="stretch"):
            if vypoctena_dan > 0:
                res_id = engine.zauctovat_dan_z_prijmu(d_do, vypoctena_dan)
                if res_id:
                    st.success(f"✅ Daň {vypoctena_dan:,.2f} Kč byla zaúčtována! (Doklad DPPO-{vybrany_rok})")
                    st.balloons()
                    # Počkáme chvilku a reloadneme, aby se aktualizovala data v grafu (pokud tam nějaký je)
            else:
                st.warning("Daň je nulová nebo záporná.")

    # ... (zbytek funkcí pro 702, 701 a Zámek nechte beze změn) ...
    with tabs[1]:
        st.subheader("Konečná roční závěrka (702)")
        # ... (zbytek kódu z minula) ...
        rok_uzav = st.number_input("Rok k uzavření", value=dnes.year, step=1, key="rok_uzav_key")
        msg_placeholder = st.empty()
        if st.button("🚀 Provést KOMPLETNÍ uzávěrku roku", type="primary", width="stretch"):
            with st.spinner("Pracuji..."):
                res = engine.provest_rocn_uzaverku_komplet(rok_uzav)
            if "✅" in res:
                msg_placeholder.success(res);
                st.balloons()
            else:
                msg_placeholder.error(res)

    with tabs[2]:
        st.subheader("Otevření nového roku (701)")
        rok_start = st.number_input("Minulý rok", value=dnes.year, step=1, key="rok_start_key")
        msg_open = st.empty()
        if st.button("✨ Otevřít nový rok", width="stretch"):
            res = engine.otevrit_novy_rok(rok_start)
            if "✅" in res:
                msg_open.success(res)
            else:
                msg_open.error(res)

    with tabs[3]:
        st.subheader("Uzamčení data")
        col_lock, col_btn = st.columns([2, 1], vertical_alignment="bottom")
        d_lock = col_lock.date_input("Uzamknout k:", value=dnes)
        if col_btn.button("🔒 Zamknout", width="stretch"):
            engine.set_datum_uzaverky(d_lock)
            st.success("Uzamčeno.")
            st.rerun()
        st.divider()
        if st.button("🔓 Odemknout", type="secondary"):
            engine.set_datum_uzaverky(None)
            st.rerun()

    with tabs[3]:  # Předpokládáme, že přidáte nový tab nebo rozšíříte stávající
        st.subheader("📦 Roční úprava zásob (Metoda B)")
        if st.session_state.metoda_zasob == 'A':
            st.info("Při metodě A probíhá účtování zásob průběžně. Zde nejsou vyžadovány žádné kroky.")
        else:
            with st.form("form_zasoby_b"):
                rok_zas = st.number_input("Rok", value=date.today().year, step=1)
                stav_mat = st.number_input("Konečný stav materiálu (112) dle inventury", min_value=0.0)
                stav_zbo = st.number_input("Konečný stav zboží (132) dle inventury", min_value=0.0)

                if st.form_submit_button("💾 Zaúčtovat stavy zásob"):
                    try:
                        res1 = engine.provest_operaci_zasoby_uzaverka(rok_zas, stav_mat, 'material')
                        res2 = engine.provest_operaci_zasoby_uzaverka(rok_zas, stav_zbo, 'zbozi')
                        if res1 and res2:
                            st.success("✅ Zásoby byly úspěšně přeceněny dle inventury.")
                    except Exception as e:
                        st.error(f"Chyba: {e}")


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
    elif modul == "Reporty":
        zobrazit_reporty()
    elif modul == "Uzávěrka":
        zobrazit_uzaverku()
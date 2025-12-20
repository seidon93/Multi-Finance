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

def format_money(x):
    """Sjednotí formátování peněz v celé aplikaci (např. 1 234 567.89 Kč)."""
    try:
        return f"{float(x):,.2f}".replace(",", " ") + " Kč"
    except:
        return "0.00 Kč"

# --- KOMPLETNÍ CSS STYLING ---
st.markdown(
    """
    <style>
    /* 1. GLOBÁLNÍ ÚPRAVA HLAVNÍHO KONTEJNERU */
    /* Vynutí, aby veškerý obsah začínal u levého okraje menu a posouval se s ním */
    div[data-testid="stCheckbox"] {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            width: 100% !important;
            margin: 0 auto !important;
            zoom: 1.5;
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


    /* Úprava pro filtry - návrat k 2 sloupcům a standardním mezerám */
    .filter-grid [data-testid="stHorizontalBlock"] {
        gap: 1.5rem !important; /* Širší mezera mezi dvěma sloupci */
        margin-bottom: 0.5rem;
    }

    .filter-grid button {
        height: 45px !important; /* Vyšší tlačítka jako na obrázku */
        font-weight: 500;
    }

    /* Vodorovný proužek pod celým filtrem */
    .filter-divider {
        border-top: 1px solid #333;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    /* --- STYL PRO TLAČÍTKO SMAZAT --- */
    div.stButton > button.delete-btn {
        background-color: #7B241C !important; /* Velmi tmavě červená */
        color: white !important;
        border: 1px solid #5D1914 !important;
        width: 100%;
    }
    div.stButton > button.delete-btn:hover {
        background-color: #943126 !important;
        border-color: #943126 !important;
    }
    /* Oranžové tlačítko pro obnovu */
    .restore-btn button {
        border-color: #28a745 !important;
        color: #28a745 !important;
    }
    .restore-btn button:hover {
        background-color: rgba(40, 167, 69, 0.1) !important;
    }

    /* Červené řádky pro smazané záznamy v tabulce */
    .deleted-row {
        color: #888 !important;
        text-decoration: line-through;
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
        ("Nová Transakce", "Přehled Účtů", "Přehled DPH", "Historie", "Reporty", "Uzávěrka", "Finanční Dashboard"),
        label_visibility="collapsed", key="main_navigation_stable"
    )
    return vyber


def formular_nova_transakce():
    # HLAVNÍ KONTEJNER S BORDEREM
    with st.container(border=True):
        st.header("Vytvořit Novou Transakci")

        # --- 1. HLAVIČKA DOKLADU ---
        c1, c2, c3 = st.columns([2, 1, 1])
        default_doklad = f"FP-{KLIENT_ID}-{date.today().strftime('%Y%m%d')}"

        doklad_cislo = c1.text_input("Číslo Dokladu", value=default_doklad)
        datum_transakce = c2.date_input("Datum Transakce", value=date.today())
        datum_splatnosti = c3.date_input("Datum Splatnosti", value=datum_transakce + timedelta(days=14))

        popis = st.text_area("Popis", placeholder="Popis účetní operace...")

        st.markdown("---")
        manualni_rezim = st.checkbox("✍️ Zadat účty ručně pro vlastní analytiku", value=False)

        c_md, c_dal = st.columns(2)

        # --- DEFINICE ÚČETNÍCH TŘÍD ---
        tridy_uctu = [
            "0 - Dlouhodobý majetek", "1 - Zásoby", "2 - Krát. fin. majetek",
            "3 - Zúčtovací vztahy", "4 - Kapitálové účty", "5 - Náklady",
            "6 - Výnosy", "7 - Závěrkové a podrozvahové účty"
        ]

        # --- LOGIKA PRO MD (Má Dáti) ---
        with c_md:
            st.subheader("MD (Má Dáti)")
            if manualni_rezim:
                ucet_md_zaklad = st.text_input("Číslo účtu MD", placeholder="např. 518.001", key="md_man")
                # PŘIDÁNO: Možnost zadat vlastní název pro nový účet
                ucet_md_nazev = st.text_input("Název účtu MD", placeholder="Vlastní název účtu...", key="md_name_man")
            else:
                trida_md_sel = st.selectbox("Třída", tridy_uctu, key="t_md")
                prefix_md = trida_md_sel.split(" - ")[0]
                zakladni_ucty_md = engine.get_zakladni_ucty_podle_tridy(prefix_md)
                vyber_zaklad_md = st.selectbox("Základní účet", zakladni_ucty_md, key="u_md_base")

                if vyber_zaklad_md:
                    cislo_zaklad_md = vyber_zaklad_md.split(" - ")[0]
                    analytika_md = engine.get_analytika_pro_ucet(cislo_zaklad_md)
                    if analytika_md:
                        moznosti_md = [f"{cislo_zaklad_md} - Bez analytiky (syntetika)"] + analytika_md
                        vyber_analytika_md = st.selectbox("↳ Podúčet", moznosti_md, key="u_md_anal")
                        ucet_md_zaklad = vyber_analytika_md.split(" - ")[0]
                    else:
                        ucet_md_zaklad = cislo_zaklad_md
                else:
                    ucet_md_zaklad = None
                ucet_md_nazev = "Nový účet MD" # Defaultní fallback

        # --- LOGIKA PRO D (Dal) ---
        with c_dal:
            st.subheader("D (Dal)")
            if manualni_rezim:
                ucet_dal_zaklad = st.text_input("Číslo účtu D", placeholder="např. 321", key="dal_man")
                # PŘIDÁNO: Možnost zadat vlastní název pro nový účet
                ucet_dal_nazev = st.text_input("Název účtu D", placeholder="Vlastní název účtu...", key="dal_name_man")
            else:
                trida_d_sel = st.selectbox("Třída", tridy_uctu, index=2, key="t_d")
                prefix_d = trida_d_sel.split(" - ")[0]
                zakladni_ucty_d = engine.get_zakladni_ucty_podle_tridy(prefix_d)
                vyber_zaklad_d = st.selectbox("Základní účet", zakladni_ucty_d, key="u_d_base")

                if vyber_zaklad_d:
                    cislo_zaklad_d = vyber_zaklad_d.split(" - ")[0]
                    analytika_d = engine.get_analytika_pro_ucet(cislo_zaklad_d)
                    if analytika_d:
                        moznosti_d = [f"{cislo_zaklad_d} - Bez analytiky (syntetika)"] + analytika_d
                        vyber_analytika_d = st.selectbox("↳ Podúčet", moznosti_d, key="u_d_anal")
                        ucet_dal_zaklad = vyber_analytika_d.split(" - ")[0]
                    else:
                        ucet_dal_zaklad = cislo_zaklad_d
                else:
                    ucet_dal_zaklad = None
                ucet_dal_nazev = "Nový účet D" # Defaultní fallback

        # --- ČÁSTKA A ZBYTEK ---
        st.markdown("---")
        col_castka, col_prev = st.columns(2)
        raw_castka = col_castka.text_input("Částka bez DPH", placeholder="1.2m, 50k", key="money_in")
        castka_bez_dph = parse_input_money(raw_castka)

        if castka_bez_dph > 0:
            col_prev.metric("K zaúčtování", format_money(castka_bez_dph))

        c_dph1, c_dph2 = st.columns(2)
        dph_opts = sorted(list(engine.get_dph_sazby().keys()), reverse=True)
        vybrana_sazba = c_dph1.selectbox("DPH %", dph_opts, index=dph_opts.index(0.0) if 0.0 in dph_opts else 0)
        smer_dph = c_dph2.radio("Typ DPH", ['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'], horizontal=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- TLAČÍTKO ULOŽIT ---
        if st.button("Uložit Transakci", type="primary", width='stretch'):
            if castka_bez_dph <= 0:
                st.error("Zadejte částku.")
            elif not ucet_md_zaklad or not ucet_dal_zaklad:
                st.error("Vyplňte oba účty.")
            else:
                try:
                    if manualni_rezim:
                        # Nyní se do DB posílá i vámi zadaný název
                        engine.zajisti_existenci_uctu(ucet_md_zaklad, ucet_md_nazev)
                        engine.zajisti_existenci_uctu(ucet_dal_zaklad, ucet_dal_nazev)

                    tid = engine.save_transakce(
                        datum=datum_transakce,
                        datum_splatnosti=datum_splatnosti,
                        popis=popis,
                        doklad_cislo=doklad_cislo,
                        ucet_md_zaklad=ucet_md_zaklad,
                        ucet_dal_zaklad=ucet_dal_zaklad,
                        castka_bez_dph=castka_bez_dph,
                        sazba_dph=vybrana_sazba,
                        smer_dph_popis=smer_dph
                    )

                    if tid:
                        st.success(f"✅ Transakce uložena! (ID {tid})")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Chyba při ukládání (zkontrolujte duplicitu čísla dokladu).")

                except ValueError as ve:
                    st.error(f"⚠️ **Účetní kontrola:** {str(ve)}")
                except Exception as e:
                    st.exception(f"FATÁLNÍ CHYBA: {e}")


def time_filter_ui():
    """Vykreslí filtry ve 2 sloupcích s pevnou vazbou na session_state (včetně Q1-Q4)."""
    st.subheader("🔍 Filtrování časového rozmezí")

    dnes = date.today()
    aktualni_rok = dnes.year

    # Inicializace session_state pro data, pokud neexistují
    if 'filter_date_from' not in st.session_state:
        st.session_state['filter_date_from'] = None
    if 'filter_date_to' not in st.session_state:
        st.session_state['filter_date_to'] = None

    def set_dates(d_from, d_to):
        st.session_state['filter_date_from'] = d_from
        st.session_state['filter_date_to'] = d_to

    with st.container(border=True):
        st.markdown('<div class="filter-grid">', unsafe_allow_html=True)

        # 1. Řada: Dnes a Tento týden
        c1, c2 = st.columns(2)
        if c1.button("Dnes", width='stretch'):
            set_dates(dnes, dnes);
            st.rerun()
        if c2.button("Tento týden", width='stretch'):
            start = dnes - timedelta(days=dnes.weekday())
            set_dates(start, start + timedelta(days=6));
            st.rerun()

        # 2. Řada: Tento měsíc a Tento rok
        c3, c4 = st.columns(2)
        if c3.button("Tento měsíc", width='stretch'):
            start_m = dnes.replace(day=1)
            next_m = dnes.replace(day=28) + timedelta(days=4)
            end_m = next_m - timedelta(days=next_m.day)
            set_dates(start_m, end_m);
            st.rerun()
        if c4.button("Tento rok", width='stretch'):
            set_dates(date(aktualni_rok, 1, 1), date(aktualni_rok, 12, 31));
            st.rerun()

        # 3. Řada: Q1 a Q2
        q1, q2 = st.columns(2)
        if q1.button("Čtvrtletí (Q1)", width='stretch'):
            set_dates(date(aktualni_rok, 1, 1), date(aktualni_rok, 3, 31));
            st.rerun()
        if q2.button("Čtvrtletí (Q2)", width='stretch'):
            set_dates(date(aktualni_rok, 4, 1), date(aktualni_rok, 6, 30));
            st.rerun()

        # 4. Řada: Q3 a Q4
        q3, q4 = st.columns(2)
        if q3.button("Čtvrtletí (Q3)", width='stretch'):
            set_dates(date(aktualni_rok, 7, 1), date(aktualni_rok, 9, 30));
            st.rerun()
        if q4.button("Čtvrtletí (Q4)", width='stretch'):
            set_dates(date(aktualni_rok, 10, 1), date(aktualni_rok, 12, 31));
            st.rerun()

        # 5. Řada: Ruční výběr dat - Pevná vazba na session_state přes unikátní klíče
        f1, f2 = st.columns(2)
        st.session_state['filter_date_from'] = f1.date_input(
            "Datum OD", value=st.session_state['filter_date_from'], key='fix_p_from_hist'
        )
        st.session_state['filter_date_to'] = f2.date_input(
            "Datum DO", value=st.session_state['filter_date_to'], key='fix_p_to_hist'
        )

        # 6. Řada: Reset filtrů
        if st.button("Reset filtrů", type="primary", width='stretch'):
            set_dates(None, None);
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state['filter_date_from'], st.session_state['filter_date_to']


def zobrazit_historii_uctu():
    st.header("Historie a Správa Transakcí")

    # Rozdělení na Aktivní záznamy a Koš pomocí záložek
    tab1, tab2 = st.tabs(["📋 Aktivní transakce", "🗑️ Koš (Smazané)"])
    from core.database import execute_query
    import time

    # --- TAB 1: AKTIVNÍ ZÁZNAMY ---
    with tab1:
        st.subheader("🔍 Vyhledat transakce")
        date_from, date_to = time_filter_ui()

        metoda = st.radio(
            "Podle čeho chcete hledat?",
            ["📅 Podle data transakce", "📄 Podle čísla dokladu (Faktury)", "👤 Podle Klienta (ID)"],
            horizontal=True, key="search_method_active"
        )

        # SQL Dotaz: Vrací 6 sloupců
        sql_base = """
            SELECT T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis, SUM(P.castka) as Objem
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.klient_id = ? AND T.is_deleted = 0
        """
        params = [KLIENT_ID]

        if metoda == "📅 Podle data transakce":
            if date_from and date_to:
                sql_base += " AND T.datum >= ? AND T.datum <= ?"
                params.extend([date_from, date_to])
            else:
                st.info("Zvolte časové období ve filtrech výše.")
                return
        elif metoda == "📄 Podle čísla dokladu (Faktury)":
            hledany_text = st.text_input("Zadejte číslo dokladu:", key="search_doc_active")
            if hledany_text:
                sql_base += " AND T.doklad_cislo LIKE ?"
                params.append(f"%{hledany_text}%")
            else:
                return

        sql_base += " GROUP BY T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis ORDER BY T.datum DESC, T.id DESC"
        rows = execute_query(sql_base, tuple(params))

        if rows:
            st.write("### Nalezené záznamy")
            df = pd.DataFrame([tuple(r) for r in rows],
                              columns=["ID", "Datum", "Splatnost", "Doklad", "Popis", "Objem"])

            df['Datum'] = pd.to_datetime(df['Datum']).dt.date
            df['Splatnost'] = pd.to_datetime(df['Splatnost']).dt.date
            df['Smazat'] = False

            edited_df = st.data_editor(
                df, width="stretch", hide_index=True, key="active_editor_interactive",
                column_config={
                    "Smazat": st.column_config.CheckboxColumn("Smazat?", default=False),
                    "Objem": st.column_config.NumberColumn("Objem (Kč)", format="%.2f"),
                    "Datum": st.column_config.DateColumn("Vystaveno"),
                    "Splatnost": st.column_config.DateColumn("Splatnost")
                }
            )

            ids_to_delete = edited_df[edited_df['Smazat'] == True]['ID'].tolist()
            if ids_to_delete:
                if st.button(f"🗑️ Přesunout {len(ids_to_delete)} záznamů do koše", type="primary",
                             width='stretch'):
                    for tid in ids_to_delete:
                        execute_query("UPDATE Transakce SET is_deleted = 1 WHERE id = ?", (tid,))
                    st.success("Záznamy byly přesunuty do koše.")
                    time.sleep(0.5)
                    st.rerun()

            st.markdown("---")
            # --- SEKCE EDITACE ---
            with st.container(border=True):
                st.subheader("✏️ Upravit vybranou transakci")
                # Výběr transakce k editaci
                transakce_map = {f"{r[3]} | {r[1]} | {r[4]} (ID: {r[0]})": r[0] for r in rows}
                vybrana_str = st.selectbox("Vyberte transakci k úpravě:", options=list(transakce_map.keys()),
                                           key="edit_select_active")

                if vybrana_str:
                    transakce_id = transakce_map[vybrana_str]
                    detail = engine.get_transakce_detail(transakce_id)

                    if detail:
                        # Unikátní klíč pro formulář zabrání nechtěným rerunům při psaní
                        with st.form(key=f"edit_form_final_{transakce_id}"):
                            st.markdown(f"**Editujete doklad:** `{detail['doklad']}`")

                            c_dok, c_dat, c_spl = st.columns([2, 1, 1])
                            new_doklad = c_dok.text_input("Číslo Dokladu", value=detail['doklad'])
                            new_datum = c_dat.date_input("Datum vystavení", value=detail['datum'])

                            # Ošetření splatnosti
                            curr_splat = detail.get('datum_splatnosti')
                            if not curr_splat: curr_splat = new_datum
                            new_splatnost = c_spl.date_input("Splatnost", value=curr_splat)

                            new_popis = st.text_area("Popis", value=detail['popis'])

                            # Sjednocené formátování peněz
                            st.write(f"Celkový objem transakce: **{format_money(detail['objem'])}**")

                            if st.form_submit_button("💾 Uložit změny", type="primary", width='stretch'):
                                # Volání opravené funkce upravit_transakci (s 10 parametry dle AccountingEngine)
                                engine.upravit_transakci(
                                    transakce_id=transakce_id,
                                    nove_datum=new_datum,
                                    nove_datum_splatnosti=new_splatnost,
                                    novy_popis=new_popis,
                                    novy_doklad=new_doklad,
                                    # Tyto hodnoty se v tomto jednoduchém formuláři nemění,
                                    # načítáme je z prvního pohybu transakce
                                    ucet_md=detail['pohyby'][0]['ucet'],
                                    ucet_dal=detail['pohyby'][-1]['ucet'],
                                    castka=detail['objem'],
                                    sazba_dph=0,  # Pro zjednodušenou editaci hlavičky
                                    smer_dph_popis='Neučtovat'
                                )
                                st.success("✅ Změny byly uloženy.")
                                time.sleep(0.8)
                                st.rerun()
        else:
            st.info("Žádné aktivní transakce neodpovídají filtrům.")

    # --- TAB 2: KOŠ ---
    with tab2:
        st.subheader("📦 Archiv smazaných transakcí")
        sql_del = """
            SELECT T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis, SUM(P.castka) as Objem
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.klient_id = ? AND T.is_deleted = 1
            GROUP BY T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis ORDER BY T.datum DESC
        """
        del_rows = execute_query(sql_del, (KLIENT_ID,))
        if del_rows:
            df_del = pd.DataFrame([tuple(r) for r in del_rows],
                                  columns=["ID", "Datum", "Splatnost", "Doklad", "Popis", "Objem"])
            df_del['Obnovit'] = False
            ed_del = st.data_editor(
                df_del, width="stretch", hide_index=True, key="trash_editor_interactive",
                column_config={
                    "Obnovit": st.column_config.CheckboxColumn("Obnovit?", default=False),
                    "Objem": st.column_config.NumberColumn("Objem (Kč)", format="%.2f"),
                    "Datum": st.column_config.DateColumn("Vystaveno"),
                    "Splatnost": st.column_config.DateColumn("Splatnost")
                }
            )

            ids_to_restore = ed_del[ed_del['Obnovit'] == True]['ID'].tolist()
            if ids_to_restore:
                if st.button("♻️ Nahrát zpět vybrané záznamy", key="restore_btn_active", width='stretch'):
                    for tid in ids_to_restore:
                        execute_query("UPDATE Transakce SET is_deleted = 0 WHERE id = ?", (tid,))
                    st.success("Záznamy obnoveny.")
                    time.sleep(0.5)
                    st.rerun()

            st.divider()
            if st.checkbox("Povolit definitivní odstranění z databáze", key="allow_hard_delete"):
                if st.button("🔥 NAVŽDY VYMAZAT CELÝ KOŠ", type="primary", width='stretch'):
                    execute_query(
                        "DELETE FROM UcetniPohyby WHERE transakce_id IN (SELECT id FROM Transakce WHERE is_deleted = 1)",
                        ())
                    execute_query("DELETE FROM Transakce WHERE is_deleted = 1", ())
                    st.error("Koš vyprázdněn.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("Koš je prázdný.")


# def zobrazit_historii_uctu():
#     st.header("Historie a Správa Transakcí")
#
#     # Rozdělení na Aktivní záznamy a Koš pomocí záložek
#     tab1, tab2 = st.tabs(["📋 Aktivní transakce", "🗑️ Koš (Smazané)"])
#     from core.database import execute_query
#
#     # --- TAB 1: AKTIVNÍ ZÁZNAMY ---
#     with tab1:
#         st.subheader("🔍 Vyhledat transakce")
#
#         # VOLÁME FILTRY HNED NA ZAČÁTKU (před returny), aby session_state držel klíče
#         date_from, date_to = time_filter_ui()
#
#         metoda = st.radio(
#             "Podle čeho chcete hledat?",
#             ["📅 Podle data transakce", "📄 Podle čísla dokladu (Faktury)", "👤 Podle Klienta (ID)"],
#             horizontal=True, key="search_method_active"
#         )
#
#         sql_base = """
#             SELECT T.id, T.datum, T.doklad_cislo, T.popis, SUM(P.castka) as Objem
#             FROM Transakce T
#             JOIN UcetniPohyby P ON T.id = P.transakce_id
#             WHERE T.klient_id = ? AND T.is_deleted = 0
#         """
#         params = [KLIENT_ID]
#
#         if metoda == "📅 Podle data transakce":
#             if date_from and date_to:
#                 sql_base += " AND T.datum >= ? AND T.datum <= ?"
#                 params.extend([date_from, date_to])
#             else:
#                 st.info("Zvolte časové období ve filtrech výše.");
#                 return
#         elif metoda == "📄 Podle čísla dokladu (Faktury)":
#             hledany_text = st.text_input("Zadejte číslo dokladu:", key="search_doc_active")
#             if hledany_text:
#                 sql_base += " AND T.doklad_cislo LIKE ?";
#                 params.append(f"%{hledany_text}%")
#             else:
#                 return
#
#         sql_base += " GROUP BY T.id, T.datum, T.doklad_cislo, T.popis ORDER BY T.datum DESC, T.id DESC"
#         rows = execute_query(sql_base, tuple(params))
#
#         if rows:
#             st.write("### Nalezené záznamy")
#             df = pd.DataFrame([tuple(r) for r in rows], columns=["ID", "Datum", "Doklad", "Popis", "Objem"])
#             df['Datum'] = pd.to_datetime(df['Datum']).dt.date
#             df['Smazat'] = False
#
#             edited_df = st.data_editor(
#                 df, width="stretch", hide_index=True, key="active_editor_interactive",
#                 column_config={"Smazat": st.column_config.CheckboxColumn("Smazat?", default=False)}
#             )
#
#             ids_to_delete = edited_df[edited_df['Smazat'] == True]['ID'].tolist()
#             if ids_to_delete:
#                 if st.button(f"🗑️ Přesunout {len(ids_to_delete)} záznamů do koše", type="primary",
#                              width='stretch'):
#                     for tid in ids_to_delete:
#                         execute_query("UPDATE Transakce SET is_deleted = 1 WHERE id = ?", (tid,))
#                     st.success("Záznamy byly přesunuty do koše.");
#                     time.sleep(0.5);
#                     st.rerun()
#
#             st.markdown("---")
#             # --- SEKCE EDITACE ---
#             st.subheader("✏️ Upravit vybranou transakci")
#             transakce_map = {f"{r[2]} | {r[1]} | {r[3]} (ID: {r[0]})": r[0] for r in rows}
#             vybrana_str = st.selectbox("Vyberte transakci k úpravě:", options=list(transakce_map.keys()),
#                                        key="edit_select_active")
#
#             if vybrana_str:
#                 transakce_id = transakce_map[vybrana_str]
#                 detail = engine.get_transakce_detail(transakce_id)
#                 if detail:
#                     with st.form(key=f"edit_form_final_{transakce_id}"):
#                         st.markdown(f"**Editujete doklad:** `{detail['doklad']}`")
#                         # (Zde pokračují pole formuláře jako v předchozím kódu...)
#                         if st.form_submit_button("💾 Uložit změny", type="primary", width='stretch'):
#                             # engine.upravit_transakci(...)
#                             st.success("✅ Upraveno.");
#                             time.sleep(0.5);
#                             st.rerun()
#         else:
#             st.info("Žádné aktivní transakce neodpovídají filtrům.")
#
#     # --- TAB 2: KOŠ ---
#     with tab2:
#         st.subheader("📦 Archiv smazaných transakcí")
#         sql_del = """
#             SELECT T.id, T.datum, T.doklad_cislo, T.popis, SUM(P.castka) as Objem
#             FROM Transakce T
#             JOIN UcetniPohyby P ON T.id = P.transakce_id
#             WHERE T.klient_id = ? AND T.is_deleted = 1
#             GROUP BY T.id, T.datum, T.doklad_cislo, T.popis ORDER BY T.datum DESC
#         """
#         del_rows = execute_query(sql_del, (KLIENT_ID,))
#         if del_rows:
#             df_del = pd.DataFrame([tuple(r) for r in del_rows], columns=["ID", "Datum", "Doklad", "Popis", "Objem"])
#             df_del['Obnovit'] = False
#             ed_del = st.data_editor(df_del, width="stretch", hide_index=True, key="trash_editor_interactive",
#                                     column_config={
#                                         "Obnovit": st.column_config.CheckboxColumn("Obnovit?", default=False)})
#             if st.button("♻️ Nahrát zpět vybrané", key="restore_btn_active"):
#                 ids_to_restore = ed_del[ed_del['Obnovit'] == True]['ID'].tolist()
#                 for tid in ids_to_restore:
#                     execute_query("UPDATE Transakce SET is_deleted = 0 WHERE id = ?", (tid,))
#                 st.rerun()
#         else:
#             st.info("Koš je prázdný.")


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

        # BANNER VÝSLEDKU - Sjednocené formátování přes format_money
        st.markdown(
            f"""
            <div style="background-color: {bg_hv}; padding: 15px; border-radius: 8px; border-left: 5px solid {barva_hv}; text-align: center; margin-bottom: 30px;">
                <h4 style="margin:0; color: #888;">VÝSLEDEK HOSPODAŘENÍ ({label_hv})</h4>
                <h1 style="margin:0; color: {barva_hv}; font-size: 2.2em;"> 💵 {format_money(hv)}</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- NÁKLADY ---
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #dc3545; padding-bottom: 5px; margin-bottom: 10px;'>Náklady</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #dc3545; margin-top: 0px;'>{format_money(data['suma_naklady'])}</h1>",
                    unsafe_allow_html=True)

        if data['naklady']:
            df = pd.DataFrame(data['naklady'])
            # Přejmenování pro přehlednost v tabulce
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            st.dataframe(
                df[['Účet', 'Název', 'Částka']],
                hide_index=True,
                width="stretch",
                column_config={"Částka": st.column_config.NumberColumn("Částka", format="%.2f")}
            )
        else:
            st.info("Žádné náklady.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- VÝNOSY ---
        st.markdown(
            f"<h3 style='border-bottom: 3px solid #28a745; padding-bottom: 5px; margin-bottom: 10px;'>Výnosy</h3>",
            unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #28a745; margin-top: 0px;'>{format_money(data['suma_vynosy'])}</h1>",
                    unsafe_allow_html=True)

        if data['vynosy']:
            df = pd.DataFrame(data['vynosy'])
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            st.dataframe(
                df[['Účet', 'Název', 'Částka']],
                hide_index=True,
                width="stretch",
                column_config={"Částka": st.column_config.NumberColumn("Částka", format="%.2f")}
            )
        else:
            st.info("Žádné výnosy.")

    # =========================================================
    # 2. ROZVAHA (BANNER SHODY + VERTIKÁLNÍ TABULKY)
    # =========================================================
    with tab_rozvaha:
        rozdil = data['suma_aktiva'] - data['suma_pasiva']
        bilance_ok = abs(rozdil) < 0.02

        if bilance_ok:
            barva_ban, bg_ban, nadpis_ban, text_ban = "#28a745", "rgba(40, 167, 69, 0.1)", "STAV BILANCE", "✅ BILANCE JE VYROVNANÁ"
        else:
            barva_ban, bg_ban, nadpis_ban, text_ban = "#dc3545", "rgba(220, 53, 69, 0.1)", "⚠️ NESHODA V BILANCI", f"ROZDÍL: {format_money(rozdil)}"

        st.markdown(
            f"""
            <div style="background-color: {bg_ban}; padding: 15px; border-radius: 8px; border-left: 5px solid {barva_ban}; text-align: center; margin-bottom: 30px;">
                <h4 style="margin:0; color: #888;">{nadpis_ban}</h4>
                <h1 style="margin:0; color: {barva_ban}; font-size: 2.2em;">{text_ban}</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- AKTIVA ---
        st.markdown(f"<h3 style='border-bottom: 3px solid #007bff; padding-bottom: 5px;'>Aktiva (Majetek)</h3>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #007bff;'>{format_money(data['suma_aktiva'])}</h1>", unsafe_allow_html=True)

        if data['aktiva']:
            df = pd.DataFrame(data['aktiva']).rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            st.dataframe(
                df[['Účet', 'Název', 'Částka']],
                hide_index=True,
                width="stretch",
                column_config={"Částka": st.column_config.NumberColumn("Částka", format="%.2f")}
            )

        # --- PASIVA ---
        st.markdown(f"<h3 style='border-bottom: 3px solid #ffc107; padding-bottom: 5px;'>Pasiva (Zdroje)</h3>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: #ffc107;'>{format_money(data['suma_pasiva'])}</h1>", unsafe_allow_html=True)

        if data['pasiva']:
            df = pd.DataFrame(data['pasiva'])[lambda x: x['ucet'] != 'HV']
            df = df.rename(columns={'ucet': 'Účet', 'nazev': 'Název', 'castka': 'Částka'})
            st.dataframe(
                df[['Účet', 'Název', 'Částka']],
                hide_index=True,
                width="stretch",
                column_config={"Částka": st.column_config.NumberColumn("Částka", format="%.2f")}
            )

    st.markdown("---")
    st.subheader("🏁 Přehled závěrkových převodů")

    with st.expander("Zobrazit detaily uzavření účtů (710 a 702)"):
        from core.database import execute_query
        sql_zaverka = """
                SELECT P.ucet, R.nazev, P.smer, P.castka
                FROM UcetniPohyby P
                JOIN Transakce T ON P.transakce_id = T.id
                LEFT JOIN UctovyRozvrh R ON P.ucet = R.cislo
                WHERE T.doklad_cislo LIKE 'UZAV-%' AND T.klient_id = ? AND T.is_deleted = 0
                ORDER BY P.ucet
            """
        try:
            zaverka_rows = execute_query(sql_zaverka, (KLIENT_ID,))
        except:
            zaverka_rows = []

        if zaverka_rows:
            df_z = pd.DataFrame([tuple(r) for r in zaverka_rows], columns=["Účet", "Název", "Směr", "Částka"])
            c_vys, c_roz = st.columns(2)

            with c_vys:
                st.info("📉 Převod do Výsledovky (710)")
                df_710 = df_z[df_z['Účet'].astype(str).str.startswith(('5', '6'))].copy()
                st.dataframe(df_710, hide_index=True, column_config={"Částka": st.column_config.NumberColumn(format="%.2f")})

            with c_roz:
                st.success("⚖️ Převod do Rozvahy (702)")
                df_702 = df_z[df_z['Účet'].astype(str).str.startswith(('0', '1', '2', '3', '4'))].copy()
                st.dataframe(df_702, hide_index=True, column_config={"Částka": st.column_config.NumberColumn(format="%.2f")})


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
    d_od, d_do = time_filter_ui()

    st.markdown('<div style="text-align: center; margin-top: 20px;"><b>Analytika v detailech</b></div>',
                unsafe_allow_html=True)
    is_detail = st.toggle("Detailní analytika", value=False, label_visibility="collapsed", key="toggle_center_final")

    data = engine.get_report_data(d_od, d_do, detailni=is_detail)

    if data:
        vsechny = data.get('aktiva', []) + data.get('pasiva', []) + \
                  data.get('naklady', []) + data.get('vynosy', [])

        if vsechny:
            df = pd.DataFrame(vsechny)
            df.columns = ['Účet', 'Název', 'Zůstatek']

            st.dataframe(
                df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Zůstatek": st.column_config.NumberColumn("Zůstatek", format="%.2f")
                }
            )

            hv = data.get('hospodarsky_vysledek', 0.0)
            st.write(f"### Průběžný hospodářský výsledek (HV): {format_money(hv)}")


def zobrazit_historii_uctu():
    st.header("Historie a Správa Transakcí")

    # Rozdělení na Aktivní záznamy a Koš
    tab1, tab2 = st.tabs(["📋 Aktivní transakce", "🗑️ Koš (Smazané)"])
    from core.database import execute_query
    import time

    # --- 1. STABILIZACE FILTRŮ (Session State) ---
    if 'filter_date_from' not in st.session_state:
        st.session_state['filter_date_from'] = date.today().replace(day=1)
    if 'filter_date_to' not in st.session_state:
        st.session_state['filter_date_to'] = date.today()

    # --- TAB 1: AKTIVNÍ ZÁZNAMY ---
    with tab1:
        # UI pro filtry s vazbou na session_state
        c1, c2 = st.columns(2)
        st.session_state['filter_date_from'] = c1.date_input("Od:", st.session_state['filter_date_from'],
                                                             key="ui_date_from")
        st.session_state['filter_date_to'] = c2.date_input("Do:", st.session_state['filter_date_to'], key="ui_date_to")

        metoda = st.radio(
            "Podle čeho chcete hledat?",
            ["📅 Podle data transakce", "📄 Podle čísla dokladu (Faktury)", "👤 Podle Klienta (ID)"],
            horizontal=True, key="search_method_active_final"
        )

        # SQL parametry
        sql_base = """
            SELECT T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis, 
                   SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) as Objem
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.klient_id = ? AND T.is_deleted = 0

        """
        params = [KLIENT_ID]

        if metoda == "📅 Podle data transakce":
            sql_base += " AND T.datum >= ? AND T.datum <= ?"

            # Zajištění, že máme platné datum, než zavoláme .strftime()
            d_from = st.session_state['filter_date_from'] if st.session_state['filter_date_from'] else date.today()
            d_to = st.session_state['filter_date_to'] if st.session_state['filter_date_to'] else date.today()

            params.extend([d_from.strftime('%Y-%m-%d'),
                           d_to.strftime('%Y-%m-%d')])
        elif metoda == "📄 Podle čísla dokladu (Faktury)":
            hledany_text = st.text_input("Zadejte číslo dokladu:", key="search_input_stable")
            if hledany_text:
                sql_base += " AND T.doklad_cislo LIKE ?"
                params.append(f"%{hledany_text}%")
            else:
                st.info("Zadejte číslo dokladu pro zobrazení výsledků.")
                rows = []

        if 'rows' not in locals():
            sql_base += " GROUP BY T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis ORDER BY T.datum DESC"
            rows = execute_query(sql_base, tuple(params))

        if rows:
            df = pd.DataFrame([tuple(r) for r in rows],
                              columns=["ID", "Datum", "Splatnost", "Doklad", "Popis", "Objem"])
            df['Datum'] = pd.to_datetime(df['Datum']).dt.date
            df['Splatnost'] = pd.to_datetime(df['Splatnost']).dt.date
            df['Smazat'] = False

            # --- EDITOR TABULKY ---
            edited_df = st.data_editor(
                df, width="stretch", hide_index=True, key="history_editor_fixed",
                column_config={
                    "ID": None,
                    "Smazat": st.column_config.CheckboxColumn("Smazat?", default=False),
                    "Objem": st.column_config.NumberColumn("Objem (Kč)", format="%.2f")
                }
            )

            # Logika smazání
            ids_to_delete = edited_df.loc[edited_df["Smazat"] == True, "ID"].tolist()

            if ids_to_delete:
                st.error(f"⚠️ Vybráno {len(ids_to_delete)} záznamů k odstranění.")
                if st.button(f"🗑️ POTVRDIT SMAZÁNÍ ({len(ids_to_delete)})", type="primary", width='stretch'):
                    for tid in ids_to_delete:
                        execute_query("UPDATE Transakce SET is_deleted = 1 WHERE id = ?", (tid,))
                    st.success(f"✅ Přesunuto do koše.")
                    time.sleep(0.5)
                    st.rerun()

            st.markdown("---")

            # --- VÁŠ KOMPLETNÍ FORMULÁŘ PRO EDITACI ---
            st.markdown("### ✏️ Upravit vybranou transakci")
            transakce_map = {f"{r[3]} | {r[1]} | {r[4]} (ID: {r[0]})": r[0] for r in rows}
            vybrana_str = st.selectbox("Vyberte transakci k úpravě:", options=list(transakce_map.keys()),
                                       key="master_edit_selectbox_stable")

            if vybrana_str:
                tid = transakce_map[vybrana_str]
                detail = engine.get_transakce_detail(tid)
                if detail:
                    with st.container(border=True):
                        st.markdown(f"**Hlavička dokladu:** `{detail['doklad']}`")

                        c_dok, c_dat, c_spl = st.columns([2, 1, 1])
                        new_doklad = c_dok.text_input("Číslo Dokladu", value=detail['doklad'], key=f"edok_{tid}")
                        new_datum = c_dat.date_input("Datum vystavení", value=detail['datum'], key=f"edat_{tid}")
                        curr_splat = detail.get('datum_splatnosti') if detail.get('datum_splatnosti') else new_datum
                        new_splatnost = c_spl.date_input("Datum splatnosti", value=curr_splat, key=f"espl_{tid}")

                        new_popis = st.text_area("Popis", value=detail['popis'], key=f"epop_{tid}")

                        st.markdown("---")

                        manualni_rezim = st.checkbox("✍️ Zadat účty ručně pro vlastní analytiku", value=False,
                                                     key=f"eman_{tid}")
                        tridy_uctu = ["0 - Dlouhodobý majetek", "1 - Zásoby", "2 - Krát. fin. majetek",
                                      "3 - Zúčtovací vztahy", "4 - Kapitálové účty", "5 - Náklady", "6 - Výnosy",
                                      "7 - Závěrkové a podrozvahové účty"]

                        c_md, c_dal = st.columns(2)

                        with c_md:
                            st.subheader("MD (Má Dáti)")
                            if manualni_rezim:
                                ucet_md_fin = st.text_input("Číslo účtu MD", value=str(detail['pohyby'][0]['ucet']),
                                                            key=f"emv_{tid}")
                                u_md_naz = st.text_input("Název účtu MD", key=f"emn_{tid}")
                            else:
                                trida_md_sel = st.selectbox("Třída MD", tridy_uctu, key=f"etm_{tid}")
                                ucty_md = engine.get_zakladni_ucty_podle_tridy(trida_md_sel.split(" - ")[0])
                                sel_md = st.selectbox("Základní účet MD", ucty_md, key=f"eum_{tid}")
                                cislo_z_md = sel_md.split(" - ")[0]
                                analytika_md = engine.get_analytika_pro_ucet(cislo_z_md)
                                if analytika_md:
                                    moznosti_md = [f"{cislo_z_md} - Bez analytiky (syntetika)"] + analytika_md
                                    vyber_anal_md = st.selectbox("↳ Podúčet MD", moznosti_md, key=f"eam_{tid}")
                                    ucet_md_fin = vyber_anal_md.split(" - ")[0]
                                else:
                                    ucet_md_fin = cislo_z_md
                                u_md_naz = None

                        with c_dal:
                            st.subheader("D (Dal)")
                            if manualni_rezim:
                                ucet_dal_fin = st.text_input("Číslo účtu D", value=str(detail['pohyby'][-1]['ucet']),
                                                             key=f"edv_{tid}")
                                u_dal_naz = st.text_input("Název účtu D", key=f"edn_{tid}")
                            else:
                                trida_dal_sel = st.selectbox("Třída D", tridy_uctu, index=3, key=f"etd_{tid}")
                                ucty_d = engine.get_zakladni_ucty_podle_tridy(trida_dal_sel.split(" - ")[0])
                                sel_d = st.selectbox("Základní účet D", ucty_d, key=f"eud_{tid}")
                                cislo_z_d = sel_d.split(" - ")[0]
                                analytika_d = engine.get_analytika_pro_ucet(cislo_z_d)
                                if analytika_d:
                                    moznosti_d = [f"{cislo_z_d} - Bez analytiky (syntetika)"] + analytika_d
                                    vyber_anal_d = st.selectbox("↳ Podúčet D", moznosti_d, key=f"ead_{tid}")
                                    ucet_dal_fin = vyber_anal_d.split(" - ")[0]
                                else:
                                    ucet_dal_fin = cislo_z_d
                                u_dal_naz = None

                        st.markdown("---")

                        cm, cs = st.columns(2)
                        new_castka = cm.text_input("Částka bez DPH", value=str(detail['objem']), key=f"ecas_{tid}")
                        new_sazba = cs.selectbox("Sazba DPH %",
                                                 sorted(list(engine.get_dph_sazby().keys()), reverse=True),
                                                 key=f"esaz_{tid}")
                        new_smer = st.radio("Typ DPH", ['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'],
                                            horizontal=True, key=f"esme_{tid}")

                        if st.button("💾 ULOŽIT ZMĚNY", type="primary", width='stretch', key=f"ebtn_{tid}"):
                            if u_md_naz: engine.zajisti_existenci_uctu(ucet_md_fin, u_md_naz)
                            if u_dal_naz: engine.zajisti_existenci_uctu(ucet_dal_fin, u_dal_naz)
                            engine.upravit_transakci(tid, new_datum, new_splatnost, new_popis, new_doklad, ucet_md_fin,
                                                     ucet_dal_fin, parse_input_money(new_castka), new_sazba, new_smer)
                            st.success("✅ Změny uloženy.")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("Žádné transakce neodpovídají filtrům.")

    # --- TAB 2: KOŠ (Původní logika) ---
    with tab2:
        st.subheader("📦 Archiv smazaných transakcí")
        sql_del = """
            SELECT T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis, 
                   SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) 
            FROM Transakce T 
            JOIN UcetniPohyby P ON T.id = P.transakce_id 
            WHERE T.klient_id = ? AND T.is_deleted = 1 
            GROUP BY T.id, T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis
            ORDER BY T.datum DESC
            """

        del_rows = execute_query(sql_del, (KLIENT_ID,))

        if del_rows:
            df_del = pd.DataFrame([tuple(r) for r in del_rows],
                                  columns=["ID", "Datum", "Splatnost", "Doklad", "Popis", "Objem"])
            df_del['Obnovit'] = False
            ed_del = st.data_editor(df_del, width="stretch", hide_index=True, key="trash_editor")

            to_res = ed_del.loc[ed_del["Obnovit"] == True, "ID"].tolist()
            if to_res:
                if st.button("♻️ NAHRÁT ZPĚT VYBRANÉ", width='stretch'):
                    for tid in to_res: execute_query("UPDATE Transakce SET is_deleted = 0 WHERE id = ?", (tid,))
                    st.rerun()

            # ... zbytek kódu pro likvidaci koše ...

            st.markdown("---")
            if st.checkbox("Povolit definitivní odstranění", key="enable_hard_delete"):
                if st.button("🔥 NAVŽDY VYMAZAT KOŠ", type="primary", width='stretch'):
                    execute_query(
                        "DELETE FROM UcetniPohyby WHERE transakce_id IN (SELECT id FROM Transakce WHERE is_deleted = 1)",
                        ())
                    execute_query("DELETE FROM Transakce WHERE is_deleted = 1", ())
                    st.error("Koš vyprázdněn.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("Koš je prázdný.")


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

            # Ponecháme hodnoty jako čísla (Decimal/float) pro st.dataframe
            vstup = data.get('vstup', Decimal('0.0'))
            vystup = data.get('vystup', Decimal('0.0'))
            rozdil = data.get('rozdil', Decimal('0.0'))

            detail_data.append({
                'Sazba': f"{sazba:.0f} %",
                'DPH Vstup (MD)': float(vstup),
                'DPH Výstup (D)': float(vystup),
                'Rozdíl': float(rozdil),
                'Účty': f"Vstup: {ucty_map['vstup']} | Výstup: {ucty_map['vystup']}"
            })

        if detail_data:
            df_detail = pd.DataFrame(detail_data)
            st.dataframe(
                df_detail,
                hide_index=True,
                width='stretch',
                column_config={
                    # Sjednocení formátu v tabulce na 2 desetinná místa
                    "DPH Vstup (MD)": st.column_config.NumberColumn("DPH Vstup (MD)", format="%.2f"),
                    "DPH Výstup (D)": st.column_config.NumberColumn("DPH Výstup (D)", format="%.2f"),
                    "Rozdíl": st.column_config.NumberColumn("Rozdíl", format="%.2f"),
                    "Účty": st.column_config.TextColumn("Použité účty")
                }
            )

    # 5. Celková povinnost (Barevný Box)
    st.subheader("Celková Daňová Povinnost")

    if celkem > Decimal('0.005'):
        typ, barva_css, final_val = "NEDOPLATEK (K ÚHRADĚ)", "#dc3545", celkem
    elif celkem < Decimal('-0.005'):
        typ, barva_css, final_val = "PŘEPLATEK (K VRÁCENÍ)", "#28a745", abs(celkem)
    else:
        typ, barva_css, final_val = "NULOVÁ POVINNOST", "#007bff", 0.0

    # Použití sjednocené funkce format_money
    suma_str = format_money(final_val)

    st.markdown(
        f"""
        <div style='border: 2px solid {barva_css}; color: {barva_css}; padding: 20px; border-radius: 10px; text-align: center;'>
            <h4 style='color: inherit; margin: 0;'>{typ}</h4>
            <h1 style='color: inherit; margin: 10px 0; font-size: 3em;'>{suma_str}</h1>
        </div>
        """,
        unsafe_allow_html=True
    )


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

        if report_data:
            hv_ucetni = report_data.get('hospodarsky_vysledek', 0.0)
            # Přičtení případných nákladů na daň zpět k HV
            naklady_dan = sum(pol['castka'] for pol in report_data['naklady'] if str(pol['ucet']).startswith('59'))
            hruby_zisk_ebt = hv_ucetni + naklady_dan
        else:
            hruby_zisk_ebt = 0.0

        # Banner pro hrubý zisk - SJEDNOCENÝ FORMÁT
        if hruby_zisk_ebt >= 0:
            barva_text, barva_bg, popisek, ikona = "#28a745", "rgba(40, 167, 69, 0.15)", "Hrubý zisk", "📈"
        else:
            barva_text, barva_bg, popisek, ikona = "#dc3545", "rgba(220, 53, 69, 0.15)", "Hrubá ztráta", "📉"

        st.markdown(f"""
            <div style="background-color: {barva_bg}; padding: 15px; border-radius: 10px; border: 2px solid {barva_text}; text-align: center; margin-bottom: 25px;">
                <h4 style="margin:0; color: {barva_text}; opacity: 0.9;">{ikona} {popisek} (před zdaněním)</h4>
                <h1 style="margin:0; color: {barva_text}; font-size: 3em; font-weight: bold;">{format_money(hruby_zisk_ebt)}</h1>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### Stanovení daňové povinnosti")
        c1, c_space, c2 = st.columns([2, 0.2, 1])
        with c1:
            zaklad_dane = st.number_input("Základ daně (Kč)", value=max(0.0, hruby_zisk_ebt), step=1000.0)
        with c2:
            sazba_dane = st.number_input("Sazba daně (%)", value=21.0, step=1.0, format="%.1f")

        vypoctena_dan = zaklad_dane * (sazba_dane / 100.0)

        # Výsledek výpočtu - SJEDNOCENÝ FORMÁT
        res_color = "#dc3545" if vypoctena_dan > 0 else "#28a745"
        res_text = "SPLATNÉ (K ÚHRADĚ)" if vypoctena_dan > 0 else "BEZ POVINNOSTI"

        st.markdown(f"""
            <div style="text-align: center; background-color: rgba(0,0,0,0.2); padding: 10px 15px; border-radius: 8px; border: 1px solid {res_color}; margin-bottom: 20px;">
                <h5 style="margin:0; color: #888;">Daňová povinnost k úhradě</h5>
                <h1 style="margin: 5px 0; color: {res_color}; font-size: 2.4em;">{format_money(vypoctena_dan)}</h1>
                <div style="color: {res_color}; font-weight: bold; text-transform: uppercase;">{res_text}</div>
            </div>
        """, unsafe_allow_html=True)

        # Opraveno width -> use_container_width
        if st.button("📝 Zaúčtovat daň (591 / 341)", type="primary", width='stretch'):
            if vypoctena_dan > 0:
                res_id = engine.zauctovat_dan_z_prijmu(d_do, vypoctena_dan)
                if res_id:
                    st.success(f"✅ Daň {format_money(vypoctena_dan)} byla zaúčtována!")
                    st.balloons()
            else:
                st.warning("Daň je nulová nebo záporná.")

    # =========================================================
    # TAB 2: ROČNÍ ZÁVĚRKA
    # =========================================================
    with tabs[1]:
        st.subheader("Konečná roční závěrka (702)")
        rok_uzav = st.number_input("Rok k uzavření", value=dnes.year, step=1, key="rok_uzav_key")
        msg_placeholder = st.empty()

        if st.button("🚀 Provést KOMPLETNÍ uzávěrku roku", type="primary", width='stretch'):
            with st.spinner("Pracuji..."):
                res = engine.provest_rocn_uzaverku_komplet(rok_uzav)

            if res and isinstance(res, str) and "✅" in res:
                msg_placeholder.success(res)
                st.balloons()
            elif res and isinstance(res, str):
                msg_placeholder.error(res)
            else:
                msg_placeholder.warning("⚠️ Uzávěrka nebyla provedena. Engine nevrátil žádná data.")

    # =========================================================
    # TAB 3: OTEVŘENÍ ROKU
    # =========================================================
    with tabs[2]:
        st.subheader("Otevření nového roku (701)")
        rok_k_otevreni = st.number_input("Rok k otevření", value=dnes.year, step=1, key="rok_start_key")
        msg_open = st.empty()
        if st.button("✨ Otevřít nový rok", width='stretch'):
            res_open = engine.otevrit_novy_rok(rok_k_otevreni)
            if res_open and "✅" in res_open:
                msg_open.success(res_open)
            else:
                msg_open.error(res_open if res_open else "Chyba při otevírání roku.")

    # =========================================================
    # TAB 4: UZAMYKÁNÍ DATA
    # =========================================================
    with tabs[3]:
        st.subheader("Uzamčení data")
        col_lock, col_btn = st.columns([2, 1], vertical_alignment="bottom")
        d_lock = col_lock.date_input("Uzamknout k:", value=aktualni_uzaverka if aktualni_uzaverka else dnes)

        if col_btn.button("🔒 Zamknout", width='stretch'):
            engine.set_datum_uzaverky(d_lock)
            st.success(f"Účetnictví bylo uzamčeno k {d_lock.strftime('%d.%m.%Y')}.")
            st.rerun()

        st.divider()
        if st.button("🔓 Odemknout účetnictví", type="secondary"):
            engine.set_datum_uzaverky(None)
            st.success("Účetnictví bylo kompletně odemčeno.")
            st.rerun()


@st.cache_data(show_spinner=False)
def cached_get_data(d_od, d_do):
    return engine.get_dashboard_data(d_od, d_do)


@st.fragment
def render_dashboard_content(df_base):
    # Tady definujeme 8 názvů pro 8 sloupců
    df_base.columns = ['datum', 'datum_splatnosti', 'subjekt', 'email', 'ico', 'typ', 'castka', 'popis']
    dnes = date.today()

    # --- FILTRY ---
    with st.container(border=True):
        st.subheader("⚙️ Upřesnit zobrazení")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            f_options = list(df_base["typ"].unique())
            f_typ = st.multiselect("Typ", options=f_options, default=f_options, key="f_typ_v_graf")
        with c2:
            min_c, max_c = float(df_base["castka"].min()), float(df_base["castka"].max())
            if min_c == max_c: max_c += 0.01
            f_range = st.slider("Rozsah (Kč)", min_c, max_c, (min_c, max_c), key="f_slider_v_graf")
        with c3:
            f_search = st.text_input("Hledat subjekt/IČO/popis", key="f_search_v_graf")

    # Filtrace
    mask = (df_base["typ"].isin(f_typ)) & (df_base["castka"].between(f_range[0], f_range[1]))
    if f_search:
        mask = mask & (df_base["subjekt"].str.contains(f_search, case=False) |
                       df_base["popis"].str.contains(f_search, case=False) |
                       df_base["ico"].astype(str).str.contains(f_search))
    df_f = df_base[mask].copy()

    # --- GRAF ---
    st.subheader("📈 Vývoj pohledávek a závazků v čase")
    if not df_f.empty:
        chart_data = df_f.groupby(['datum', 'typ'])['castka'].sum().unstack(fill_value=0)
        color_map = {"Závazek": "#dc3545", "Pohledávka": "#28a745"}
        current_colors = [color_map[col] for col in chart_data.columns if col in color_map]
        st.line_chart(chart_data, color=current_colors)

    # --- METRIKY ---
    pohl = df_f[df_f["typ"] == "Pohledávka"]["castka"].sum()
    zav = df_f[df_f["typ"] == "Závazek"]["castka"].sum()

    m1, m2 = st.columns(2)
    m1.metric("Pohledávky", format_money(pohl))
    m2.metric("Závazky", format_money(zav))

    # Banner bilance
    st.markdown(f"""
        <div style="background-color: rgba(0, 123, 255, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; text-align: center; margin-bottom: 20px;">
            <h5 style="margin:0; color: #007bff; opacity: 0.8;">AKTUÁLNÍ FINANČNÍ BILANCE</h5>
            <h1 style="margin:0; color: #007bff; font-weight: bold;">{format_money(pohl - zav)}</h1>
        </div>
    """, unsafe_allow_html=True)

    # --- TABULKA ---
    def style_dashboard_rows(row):
        text_color = '#28a745' if row.typ == 'Pohledávka' else '#dc3545'
        base_style = f'color: {text_color}; font-weight: bold;'
        if row.datum_splatnosti and not pd.isna(row.datum_splatnosti):
            d_splat = row.datum_splatnosti
            if isinstance(d_splat, str): d_splat = pd.to_datetime(d_splat).date()
            if d_splat < dnes:
                return [base_style + ' background-color: rgba(220, 53, 69, 0.1);'] * len(row)
        return [base_style] * len(row)

    st.dataframe(
        df_f.style.apply(style_dashboard_rows, axis=1),
        width='stretch', hide_index=True,
        column_config={
            "castka": st.column_config.NumberColumn("Částka (Kč)", format="%.2f"),
            "subjekt": st.column_config.TextColumn("Partner"),
            "popis": st.column_config.TextColumn("Popis transakce"),
            "ico": st.column_config.TextColumn("IČO"),
            "datum_splatnosti": st.column_config.DateColumn("Splatnost"),
            "datum": st.column_config.DateColumn("Vystaveno")
        }
    )


def zobrazit_working_capital_sekci(datum_k):
    wc = engine.get_working_capital_metrics(datum_k)

    st.subheader("📦 Pracovní kapitál")
    c1, c2, c3 = st.columns(3)
    c1.metric("Hrubý pracovní kapitál", format_money(wc['gross_wc']))
    c2.metric("Čistý pracovní kapitál", format_money(wc['net_wc']))
    c3.metric("Likvidní WC (Cash)", format_money(wc['liquid_wc']))

    with st.expander("Detailní rozdělení (Permanentní vs. Sezónní)"):
        p_col, s_col = st.columns(2)
        perm = float(wc['gross_wc']) * 0.7
        seas = float(wc['gross_wc']) * 0.3
        p_col.info(f"**Permanentní složka (70%)**\n\n{format_money(perm)}")
        s_col.warning(f"**Sezónní složka (30%)**\n\n{format_money(seas)}")

def zobrazit_financni_dashboard():
    st.header("📊 Finanční Dashboard")

    # 1. ČASOVÉ FILTRY
    d_od, d_do = time_filter_ui()

    if d_do:
        zobrazit_working_capital_sekci(d_do)
        st.divider()
        zobrazit_trend_financi(d_od, d_do)
        st.divider()

    if not d_od or not d_do:
        st.info("Zvolte časové období ve filtrech pro zobrazení finančních dat.")
        return

    # 2. NAČTENÍ DAT
    raw_data = engine.get_dashboard_data(d_od, d_do)

    if not raw_data:
        st.warning("V tomto období nejsou žádné reálné obchodní pohledávky ani závazky.")
        return

    # 3. VYTVOŘENÍ DATAFRAME (Důležité: Pořadí musí sedět s SQL dotazem!)
    # SQL vrací: datum, datum_splatnosti, subjekt, email, ico, typ, castka, popis
    df_base = pd.DataFrame(
        [tuple(r) for r in raw_data],
        columns=['datum', 'datum_splatnosti', 'subjekt', 'email', 'ico', 'typ', 'castka', 'popis']
    )

    # Převod na čisté datum pro správné zobrazení
    df_base['datum'] = pd.to_datetime(df_base['datum']).dt.date
    if 'datum_splatnosti' in df_base.columns:
        df_base['datum_splatnosti'] = pd.to_datetime(df_base['datum_splatnosti']).dt.date

    # 4. VOLÁNÍ VYKRESLOVACÍ FUNKCE (Bez tohoto řádku nic neuvidíte!)
    render_dashboard_content(df_base)


import plotly.graph_objects as go

def zobrazit_trend_financi(d_od, d_do):
    st.subheader("📈 Vývoj příjmů a výdajů v čase")
    data = engine.get_income_expense_trend(d_od, d_do)

    if not data:
        st.info("Pro vybrané období nejsou k dispozici žádná data pro graf.")
        return

    try:
        # Vytvoření DataFrame
        df = pd.DataFrame(data, columns=['Měsíc', 'Příjmy', 'Výdaje'])
        df['Saldo'] = df['Příjmy'] - df['Výdaje']

        # Extrakce dat pro poslední záznam
        posledni_radek = df.iloc[-1]
        aktualni_mesic_nazev = posledni_radek['Měsíc']
        akt_prijmy = posledni_radek['Příjmy']
        akt_vydaje = posledni_radek['Výdaje']
        akt_saldo = posledni_radek['Saldo']
        celkove_saldo_obdobi = df['Saldo'].sum()

        # Společné nastavení layoutu pro oba grafy
        shared_layout = dict(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            showlegend=False,
            xaxis=dict(
                type='category',  # Toto zajistí, že se zobrazí přesně ty popisky, co jsou v DF
                showgrid=False,
                showline=False,
                zeroline=False
            ),
            yaxis=dict(
                showline=False,
                ticks="",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor='#C0C0C0',
                gridcolor='#333'
            )
        )

        # --- 1. GRAF PŘÍJMY A VÝDAJE ---
        st.markdown(
            f"Aktuální měsíc ({aktualni_mesic_nazev}): "
            f"<span style='color:#28a745; font-weight:bold;'>+{format_money(akt_prijmy)}</span> | "
            f"<span style='color:#dc3545; font-weight:bold;'>-{format_money(akt_vydaje)}</span>",
            unsafe_allow_html=True
        )

        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df['Měsíc'], y=df['Příjmy'], name="Příjmy", marker_color="#28a745", marker_line_width=0))
        fig1.add_trace(go.Bar(x=df['Měsíc'], y=df['Výdaje'], name="Výdaje", marker_color="#dc3545", marker_line_width=0))

        fig1.update_layout(**shared_layout)
        fig1.update_layout(barmode='group', showlegend=True, bargap=0.2, bargroupgap=0.05,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,))
        st.plotly_chart(fig1, width='stretch', config={'displayModeBar': False})

        # --- 2. GRAF SALDA ---
        st.subheader(f"📊 Detailní měsíční saldo")

        barva_text_mesic = "#28a745" if akt_saldo >= 0 else "#dc3545"
        st.markdown(
            f"Aktuální měsíc ({aktualni_mesic_nazev}): <span style='color:{barva_text_mesic}; font-weight:bold; font-size:1.1em;'>{format_money(akt_saldo)}</span> | "
            f"Celkové období: **{format_money(celkove_saldo_obdobi)}**",
            unsafe_allow_html=True
        )

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df['Měsíc'],
            y=df['Saldo'],
            marker_color=df['Saldo'].apply(lambda x: "#28a745" if x >= 0 else "#dc3545"),
            marker_line_width=0
        ))

        fig2.update_layout(**shared_layout, )
        st.plotly_chart(fig2, width='stretch', config={'displayModeBar': False}, )

    except Exception as e:
        st.error(f"Chyba při vykreslování trendu: {e}")



# 3. Rozcestník na konci souboru
if __name__ == "__main__":
    modul = zobrazit_header()

    if modul == "Finanční Dashboard":  # MUSÍ BÝT PŘESNĚ STEJNĚ JAKO V RADIO
        zobrazit_financni_dashboard()
    elif modul == "Nová Transakce":
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
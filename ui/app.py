import sys
import os
from datetime import date, timedelta
import streamlit as st
import pandas as pd
from decimal import Decimal  # Zajistit, že Decimal je k dispozici pro DPH

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

# Inicializace účetního enginu (globálně)
# Předpokládáme, že tato třída je správně napojena na Vaši databázi.
engine = AccountingEngine(klient_id=KLIENT_ID)

# --- CSS STYLING (Nezměněno) ---
st.markdown(
    """
    <style>
    /* Obecné styly pro mřížku */
    [data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 150px;
        max-width: 300px;
    }

    /* Vizuální styly pro text v hlavičce Historie */
    .zustatek-kladny {
        color: #28a745 !important; /* Zelená */
        font-size: 1.15em !important;
        font-weight: bold !important;
    }
    .zustatek-zaporny {
        color: #dc3545 !important; /* Červená */
        font-size: 1.15em !important;
        font-weight: bold !important;
    }

    /* Barva pro název a číslo účtu v hlavičce detailu */
    .ucet-nazev {
        color: #007bff !important; /* Tmavě modrá */
        font-size: 1.25em !important; 
        font-weight: bold !important;
        margin-bottom: 0px;
    }

    p {
        margin-bottom: 5px; 
        margin-top: 5px;
    }

    /* --- PRAVIDLO PRO ČERVENÉ TLAČÍTKO RESET --- */
    div.stButton > button[kind="primary"] {
        background-color: #A93226 !important; /* Tmavě červená */
        color: white !important;
        border: 1px solid #A93226 !important;
        border-radius: 5px;
        transition: background-color 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #C0392B !important; 
        border-color: #C0392B !important;
    }
    /* DPH Povinnost styling */
    .dph-box {
        padding: 10px; 
        border: 2px solid; 
        border-radius: 5px; 
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)


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
    """Vytvoří hlavičku a navigační menu."""
    st.title("💰 Multi-Finance Účetní Systém")
    st.sidebar.title("Navigace")

    vyber = st.sidebar.radio(
        "Zvolte Modul:",
        ("Nová Transakce", "Přehled Účtů", "Přehled DPH", "Historie", "Reporty")
    )
    return vyber


def formular_nova_transakce():
    st.header("Vytvořit Novou Transakci")

    #  --- UPDATE DB TLAČÍTKO (Jen pro prvotní naplnění) ---
    # with st.expander("⚙️ Správa databáze"):
    #     if st.button("Nahrát kompletní účtovou osnovu (cca 80 účtů)"):
    #         zprava = engine.inicializuj_uctovy_rozvrh()
    #         st.success(zprava)
    #         # st.rerun() # Odkomentujte, pokud chcete hned refreshnout stránku

    # --- DEFINICE ÚČETNÍCH TŘÍD PRO VÝBĚR ---
    tridy_uctu = [
        "0 - Dlouhodobý majetek",
        "1 - Zásoby",
        "2 - Krát. fin. majetek a pen. prostředky",
        "3 - Zúčtovací vztahy",
        "4 - Kapitálové účty a dlouhodobé závazky",
        "5 - Náklady",
        "6 - Výnosy",
        "7 - Závěrkové a podrozvahové účty",
    ]

    # --- 1. HLAVIČKA DOKLADU ---
    c1, c2 = st.columns(2)
    default_doklad = f"FP-{KLIENT_ID}-{date.today().strftime('%Y%m%d')}"
    doklad_cislo = c1.text_input("Číslo Dokladu", value=default_doklad)
    datum_transakce = c2.date_input("Datum Transakce", value=date.today())
    popis = st.text_area("Popis", placeholder="Popis účetní operace...")

    st.markdown("---")

    # === PŘEPÍNAČ REŽIMU ZADÁVÁNÍ ===
    manualni_rezim = st.checkbox("✍️ Zadat účty ručně (pro vlastní analytiku)", value=False)

    c_md, c_dal = st.columns(2)

    # --- LOGIKA PRO MD ---
    with c_md:
        st.subheader("MD (Má Dáti)")
        if manualni_rezim:
            ucet_md_zaklad = st.text_input("Číslo účtu MD", placeholder="např. 518.001")
            nazev_md_manual = st.text_input("Název účtu MD (pro nový účet)", placeholder="Volitelné", key="n_md")
        else:
            # Výběrový režim
            trida_md_sel = st.selectbox("Třída", tridy_uctu, key="t_md")
            prefix_md = trida_md_sel.split(" - ")[0]
            ucty_md_list = engine.get_ucty_podle_tridy(prefix_md)

            if ucty_md_list:
                vyber_md = st.selectbox("Účet", ucty_md_list, key="u_md")
                ucet_md_zaklad = vyber_md.split(" - ")[0].strip()
            else:
                st.warning("Žádné účty.")
                ucet_md_zaklad = None

    # --- LOGIKA PRO D ---
    with c_dal:
        st.subheader("D (Dal)")
        if manualni_rezim:
            ucet_dal_zaklad = st.text_input("Číslo účtu D", placeholder="např. 321")
            nazev_d_manual = st.text_input("Název účtu D (pro nový účet)", placeholder="Volitelné", key="n_d")
        else:
            # Výběrový režim (Defaultně třída 3 nebo 2)
            trida_d_sel = st.selectbox("Třída", tridy_uctu, index=2, key="t_d")
            prefix_d = trida_d_sel.split(" - ")[0]
            ucty_d_list = engine.get_ucty_podle_tridy(prefix_d)

            if ucty_d_list:
                vyber_d = st.selectbox("Účet", ucty_d_list, key="u_d")
                ucet_dal_zaklad = vyber_d.split(" - ")[0].strip()
            else:
                st.warning("Žádné účty.")
                ucet_dal_zaklad = None

    # --- ČÁSTKA A ZBYTEK ---
    st.markdown("---")
    col_castka, col_prev = st.columns([1, 1])
    raw_castka = col_castka.text_input("Částka bez DPH", placeholder="1.2m, 50k")
    castka_bez_dph = parse_input_money(raw_castka)
    if castka_bez_dph > 0:
        col_prev.metric("Částka", f"{castka_bez_dph:,.2f} Kč".replace(",", " ").replace(".", ","))

    c_dph1, c_dph2 = st.columns(2)
    dph_sazby = engine.get_dph_sazby()
    dph_opts = sorted(list(dph_sazby.keys()), reverse=True)
    vybrana_sazba = c_dph1.selectbox("DPH %", dph_opts, index=dph_opts.index(0.0) if 0.0 in dph_opts else 0)
    smer_dph = c_dph2.radio("Typ DPH", ['Neučtovat', 'DPH na VSTUPU (MD)', 'DPH na VÝSTUPU (D)'])

    # --- ULOŽENÍ ---
    st.markdown("")
    if st.button("Uložit Transakci", type="primary", use_container_width=True):
        if castka_bez_dph <= 0:
            st.error("Zadejte částku.")
        elif not ucet_md_zaklad or not ucet_dal_zaklad:
            st.error("Vyplňte oba účty.")
        else:
            try:
                # 1. Pokud je manuální režim, zajistíme, že účty v DB existují
                if manualni_rezim:
                    n_md = nazev_md_manual if nazev_md_manual else "Ručně vytvořený účet"
                    n_d = nazev_d_manual if nazev_d_manual else "Ručně vytvořený účet"

                    engine.zajisti_existenci_uctu(ucet_md_zaklad, n_md)
                    engine.zajisti_existenci_uctu(ucet_dal_zaklad, n_d)

                # 2. Uložení
                tid = engine.save_transakce(
                    datum=datum_transakce, popis=popis, doklad_cislo=doklad_cislo,
                    ucet_md_zaklad=ucet_md_zaklad, ucet_dal_zaklad=ucet_dal_zaklad,
                    castka_bez_dph=castka_bez_dph, sazba_dph=vybrana_sazba, smer_dph_popis=smer_dph
                )  # <--- ZDE BYLA CHYBA (DOPLNĚNA ZÁVORKA)

                if tid:
                    st.success(f"✅ Transakce uložena! (ID {tid})")
                else:
                    st.error("❌ Chyba při ukládání (zkontrolujte duplicitu čísla dokladu).")

            except Exception as e:
                st.exception(f"FATÁLNÍ CHYBA: {e}")


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

        if c1.button("Dnes", use_container_width=True):
            set_dates(dnes, dnes)

        if c2.button("Tento týden", use_container_width=True):
            start_week = get_start_of_week(dnes)
            end_week = start_week + timedelta(days=6)
            set_dates(start_week, end_week)

        if c3.button("Tento měsíc", use_container_width=True):
            start_month = get_start_of_month(dnes)
            end_month = get_end_of_month(dnes)
            set_dates(start_month, end_month)

        if c4.button("Tento rok", use_container_width=True):
            set_dates(get_start_of_year(dnes), get_end_of_year(dnes))

        # --- NOVÉ: Řádek 2: Čtvrtletí ---
        q1, q2, q3, q4 = st.columns(4)

        # 1. Čtvrtletí (leden - březen)
        if q1.button("1. Čtvrtletí (Q1)", use_container_width=True):
            set_dates(date(aktualni_rok, 1, 1), date(aktualni_rok, 3, 31))

        # 2. Čtvrtletí (duben - červen)
        if q2.button("2. Čtvrtletí (Q2)", use_container_width=True):
            set_dates(date(aktualni_rok, 4, 1), date(aktualni_rok, 6, 30))

        # 3. Čtvrtletí (červenec - září)
        if q3.button("3. Čtvrtletí (Q3)", use_container_width=True):
            set_dates(date(aktualni_rok, 7, 1), date(aktualni_rok, 9, 30))

        # 4. Čtvrtletí (říjen - prosinec)
        if q4.button("4. Čtvrtletí (Q4)", use_container_width=True):
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

        if col_reset.button("Reset filtrů", type="primary", use_container_width=True):
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
                <h1 style="margin:0; color: {barva_hv}; font-size: 2.2em;">{hv:,.2f} Kč</h1>
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
            st.dataframe(df, hide_index=True, use_container_width=True)
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
            st.dataframe(df, hide_index=True, use_container_width=True)
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
            text_ban = "BILANCE JE VYROVNANÁ (OK)"
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
                use_container_width=True,
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
                    use_container_width=True,
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
    st.header("Hlavní Přehled Účtů")

    # --- 1. ČASOVÝ FILTR ---
    date_from, date_to = time_filter_ui()

    # --- 2. NAČTENÍ DAT ---
    zustatky_data = engine.spocti_zustatky(datum_od=date_from, datum_do=date_to)

    if not zustatky_data:
        st.info("V zadaném období nebyly nalezeny žádné pohyby.")
        return

    # --- 3. PŘÍPRAVA DAT PRO TABULKU ---
    data_pro_tabulku = []

    # Seznam účtů, které chceme vidět VŽDY (VIP)
    vip_ucty = ['211', '221', '311', '321']

    for ucet, castka in zustatky_data.items():
        # Podmínka: Zobrazit, pokud je zůstatek nenulový NEBO je to VIP účet
        if abs(castka) > 0.005 or ucet in vip_ucty:
            nazev = engine.get_ucet_nazev(ucet)
            data_pro_tabulku.append({
                "Účet": ucet,
                "Název": nazev,
                "Zůstatek Raw": castka,
                "Zůstatek": castka
            })

    # --- 4. VYTVOŘENÍ DATAFRAME ---
    if data_pro_tabulku:
        df = pd.DataFrame(data_pro_tabulku)

        # Seřazení podle čísla účtu
        df = df.sort_values(by='Účet')

        # Formátování měny
        df['Zůstatek'] = df['Zůstatek'].apply(
            lambda x: f"{x:,.2f} Kč".replace(",", " ").replace(".", ",")
        )

        # --- NOVÝ NADPIS ---
        st.subheader("Detailní přehled účtů")

        # --- VYKRESLENÍ TABULKY ---
        # Odstraněn parametr 'height', aby se tabulka přizpůsobila obsahu
        st.dataframe(
            df[['Účet', 'Název', 'Zůstatek']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("Žádné účty nemají v tomto období nenulový zůstatek.")


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
                use_container_width=True,
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
    import pandas as pd

    st.header("Historie Účtu (Detailní Přehled)")

    date_from, date_to = time_filter_ui()

    zustatky_all_filtrovane = engine.spocti_zustatky(datum_od=None, datum_do=date_to)
    zustatky_all_komplet = engine.spocti_zustatky()
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

                # Formátování na string s měnou
                df_pohyby['Částka'] = df_pohyby['Částka'].apply(lambda x: f'{x:,.2f} Kč')

            required_cols = ['Datum', 'Doklad Číslo', 'Popis Transakce', 'Částka']
            if 'Název Účtu' in df_pohyby.columns:
                required_cols.append('Název Účtu')

            df_pohyby = df_pohyby[required_cols]
            st.dataframe(df_pohyby, width='stretch', hide_index=True)

        else:
            st.info(f"Na účtu {ucet_k_zobrazeni} nebyly nalezeny žádné pohyby v období od {date_from} do {date_to}.")


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
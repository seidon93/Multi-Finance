import sys
import os
from datetime import date
import streamlit as st
import pandas as pd

# Zajištění, že se importují moduly z nadřazeného adresáře (core)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Oprava: sys.path.append(os.path.join(current_dir, '..')) je spolehlivější
sys.path.append(os.path.join(current_dir, os.pardir))

from dotenv import load_dotenv
from core.accounting_logic import AccountingEngine

load_dotenv()
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Předpokládáme, že ID klienta je prozatím 1
KLIENT_ID = 1

# Inicializace účetního enginu pro daného klienta (globálně)
engine = AccountingEngine(klient_id=KLIENT_ID)

# --- CSS STYLING (FIX BAREV S !important) ---
st.markdown(
    """
    <style>
    /* Obecné styly pro mřížku (i když se teď nepoužívá, necháme je pro případné znovuzavedení) */
    [data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 150px;
        max-width: 300px;
    }

    /* Vizuální styly pro text v hlavičce Historie */
    .zustatek-kladny {
        color: #28a745 !important; /* Zelená (výnos/aktivum) */
        font-size: 1.15em !important;
        font-weight: bold !important;
    }
    .zustatek-zaporny {
        color: #dc3545 !important; /* Červená (náklad/závazek) */
        font-size: 1.15em !important;
        font-weight: bold !important;
    }

    /* Barva pro název a číslo účtu v hlavičce detailu (Změněno na Tmavě modrou) */
    .ucet-nazev {
        color: #007bff !important; /* Tmavě modrá pro odlišení */
        font-size: 1.25em !important; /* Mírně zvětšeno */
        font-weight: bold !important;
        margin-bottom: 0px; /* Přiblíží název k zůstatku */
    }

    /* Zajištění, že p tagy s textem účtu nezanechávají zbytečné mezery */
    p {
        margin-bottom: 5px; 
        margin-top: 5px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# --- KONEC CSS STYLINGU ---


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


# soubor: ui/app.py

def zobrazit_prehled_uctu():
    st.header("Přehled Zůstatků na Účtech")

    # --- VLOŽENÍ ČASOVÉHO FILTRU ---
    # Zde jsou získány proměnné date_from a date_to
    date_from, date_to = time_filter_ui()
    st.markdown("---")  # Oddělení filtru od přehledu

    # Získání zůstatků s filtrem
    zustatky_all = engine.spocti_zustatky(datum_od=date_from, datum_do=date_to)

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
        # VOLÁNÍ S FILTREM I ZDE
        zustatky_data = engine.spocti_zustatky(datum_od=date_from, datum_do=date_to)

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
    st.header("Daňová Povinnost DPH")
    date_from, date_to = time_filter_ui()
    st.markdown("---")

    if st.button("Vypočítat DPH Povinnost"):
        dph_data = engine.spocti_prehled_dph(datum_od=date_from, datum_do=date_to)
        celkem = dph_data.pop('CELKEM')

        # --- Tabulka zůstatků po sazbách ---
        st.subheader("Detailní Přehled po Sazbách")

        detail_data = []
        for sazba, data in dph_data.items():
            # Získání názvů analytických účtů pro lepší kontext
            ucty_map = engine.get_dph_sazby()[sazba]

            detail_data.append({
                'Sazba (%)': f"{sazba:.2f}",
                f'DPH VSTUP ({ucty_map["vstup"]})': data['vstup'],
                f'DPH VÝSTUP ({ucty_map["vystup"]})': data['vystup'],
                'Rozdíl DPH (Závazek - Pohledávka)': data['rozdil']
            })

        df_detail = pd.DataFrame(detail_data)

        # --- OPRAVA: Odstranění NaN a Formátování ---
        df_detail = df_detail.fillna(0.0)

        for col in df_detail.columns:
            if col not in ['Sazba (%)']:
                df_detail[col] = df_detail[col].apply(lambda x: f'{x:,.2f} Kč')

        # --- ZOBRAZENÍ: Odstranění indexu a roztažení ---
        st.dataframe(
            df_detail,
            hide_index=True,
            width='stretch'
        )

        # --- Celková povinnost ---
        st.subheader("Celková Daňová Povinnost")

        if celkem > 0:
            typ = "NEDOPLATEK (K ÚHRADĚ)"
            barva = "red"
        elif celkem < 0:
            typ = "PŘEPLATEK (K VRÁCENÍ)"
            barva = "green"
        else:
            typ = "NULOVÁ POVINNOST"
            barva = "blue"

        st.markdown(
            f"""
            <div style='
                padding: 10px; 
                border: 2px solid {barva}; 
                border-radius: 5px; 
                text-align: center;
            '>
                <h4>{typ}</h4>
                <h1>{celkem:,.2f} Kč</h1>
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

                df_pohyby['Částka'] = df_pohyby['Částka'].apply(lambda x: f'{x:,.2f} Kč')

            required_cols = ['Datum', 'Doklad Číslo', 'Popis Transakce', 'Částka']
            if 'Název Účtu' in df_pohyby.columns:
                required_cols.append('Název Účtu')

            df_pohyby = df_pohyby[required_cols]
            st.dataframe(df_pohyby, width='stretch', hide_index=True)

        else:
            st.info(f"Na účtu {ucet_k_zobrazeni} nebyly nalezeny žádné pohyby v období od {date_from} do {date_to}.")




def time_filter_ui():
    """Vykreslí tlačítka a výběr rozmezí pro filtrování času."""
    st.markdown("---")  # Oddělovač
    st.subheader("Filtrování časového rozmezí")

    dnes = date.today()

    # Uložení stavu vybraných dat do session state
    if 'filter_date_from' not in st.session_state:
        st.session_state['filter_date_from'] = None
    if 'filter_date_to' not in st.session_state:
        st.session_state['filter_date_to'] = None

    # --- Definice funkcí pro časové skoky (ZŮSTÁVÁ STEJNÁ) ---
    def set_dates(d_from, d_to):
        st.session_state['filter_date_from'] = d_from
        st.session_state['filter_date_to'] = d_to
        st.rerun()

    def get_start_of_week(d):
        from datetime import timedelta
        return d - timedelta(days=d.weekday())

    def get_start_of_month(d):
        return d.replace(day=1)

    def get_start_of_year(d):
        return d.replace(month=1, day=1)

    # --- PŘEHLEDNÁ MŘÍŽKA S FILTRY ---
    # Řádek 1: Tlačítka pro rychlou volbu (4 sloupce stejné šířky)
    col1, col2, col3, col4 = st.columns(4)

    # 1. Dnes
    if col1.button("Dnes", key='filter_dnes'):
        set_dates(dnes, dnes)

    # 2. Aktuální Týden
    if col2.button("Týden (Po - Dnes)", key='filter_tyden'):
        start_week = get_start_of_week(dnes)
        set_dates(start_week, dnes)

    # 3. Aktuální Měsíc
    if col3.button("Měsíc", key='filter_mesic'):
        start_month = get_start_of_month(dnes)
        set_dates(start_month, dnes)

    # 4. Aktuální Rok
    if col4.button("Rok", key='filter_rok'):
        start_year = get_start_of_year(dnes)
        set_dates(start_year, dnes)

    # Řádek 2: Ruční výběr rozmezí a Reset (Rozložení: Datum OD, Datum DO, Reset)
    col_from, col_to, col_reset = st.columns([1, 1, 0.5])

    # 5. Kalendářní rozmezí OD
    date_from_input = col_from.date_input(
        "Datum OD",
        value=st.session_state['filter_date_from'] if st.session_state['filter_date_from'] else None,
        key='input_date_from'
    )
    # 6. Kalendářní rozmezí DO
    date_to_input = col_to.date_input(
        "Datum DO",
        value=st.session_state['filter_date_to'] if st.session_state['filter_date_to'] else None,
        key='input_date_to'
    )

    # 7. Reset
    # Tlačítko se typicky centruje s políčky, aby to vypadalo dobře
    # Použijeme vertikální mezeru nad tlačítkem pro zarovnání s date_input
    col_reset.markdown("<br>", unsafe_allow_html=True)
    if col_reset.button("Reset Filtru", key='filter_reset'):
        set_dates(None, None)  # Zrušení filtru

    st.markdown("---")  # Oddělovač

    # --- Zpracování ručního výběru (ZŮSTÁVÁ STEJNÉ) ---

    # Uložení ručně vybraných dat, pokud se změnila
    if date_from_input != st.session_state['filter_date_from'] or date_to_input != st.session_state['filter_date_to']:
        st.session_state['filter_date_from'] = date_from_input
        st.session_state['filter_date_to'] = date_to_input
        st.rerun()

    # Vrátíme aktuálně platné filtry
    return st.session_state['filter_date_from'], st.session_state['filter_date_to']

    st.markdown("---")  # Oddělovač

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
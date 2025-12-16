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
        color: #17a2b8 !important; /* Tyrkysová/Modrá pro odlišení */
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


def zobrazit_prehled_uctu():
    st.header("Přehled Zůstatků na Účtech")

    # --- 1. SEZNAM SLEDOVANÝCH ÚČTŮ (FILTROVANÝ PŘEHLED) ---
    st.subheader("Přehled Sledovaných Účtů (Klíčová Analytika)")

    sledovane_ucty = [
        '221', '311', '602', '511', '321',
        '343.1.21', '343.2.21', '343.1.12', '343.2.12', '343.1.00', '343.2.00',
        '343.1', '343.2'
    ]

    data = []
    for ucet in sledovane_ucty:
        zustatek = engine.get_zustatek_uctu(ucet)
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
        st.info("Žádné zůstatky na sledovaných účtech.")

    # --- 2. SYNTERICKÁ ÚČETNÍ KNIHA (AGREGACE) ---
    st.subheader("Syntetická Účetní Kniha (Všechny zůstatky)")

    if st.button("Obnovit Agregované Zůstatky"):
        zustatky_data = engine.spocti_zustatky()

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
            st.warning("Nelze načíst nebo spočítat agregované zůstatky.")


def zobrazit_prehled_dph():
    st.header("Daňová Povinnost DPH")

    if st.button("Vypočítat DPH Povinnost"):
        dph_data = engine.spocti_prehled_dph()
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
    st.header("Historie Účtu (Detailní Přehled)")

    # 1. Získání seznamu všech účtů s nenulovým zůstatkem
    zustatky_all = engine.spocti_zustatky()
    seznam_uctu_s_pohybem = [ucet for ucet, zustatek in zustatky_all.items() if abs(zustatek) > 0.005]
    seznam_uctu_s_pohybem = sorted(seznam_uctu_s_pohybem)

    if not seznam_uctu_s_pohybem:
        st.info("Žádný účet nemá aktuálně nenulový zůstatek pro zobrazení historie.")
        return

    # --- FILTRACE ÚČTŮ POMOCÍ MULTISELECTU ---
    st.subheader("1. Výběr účtů pro detailní přehled")

    vybrane_ucty_k_zobrazeni = st.multiselect(
        "Vyberte účty, jejichž historii chcete zobrazit:",
        options=seznam_uctu_s_pohybem,
        # Předvybereme klíčové účty nebo všechny jako výchozí
        default=[u for u in ['221', '321', '311'] if u in seznam_uctu_s_pohybem] or seznam_uctu_s_pohybem
    )

    if not vybrane_ucty_k_zobrazeni:
        st.warning("Prosím, vyberte alespoň jeden účet k zobrazení.")
        return

    # --- DETAILNÍ PŘEHLED VYBRANÝCH ÚČTŮ ---
    st.subheader("2. Detailní pohyby")

    # Projdeme každý vybraný účet a zobrazíme jeho historii
    for ucet_k_zobrazeni in vybrane_ucty_k_zobrazeni:

        pohyby = engine.get_pohyby_uctu(ucet_k_zobrazeni)
        aktualni_zustatek = zustatky_all.get(ucet_k_zobrazeni, 0)

        # Určení CSS třídy pro barevné odlišení zůstatku
        css_class_zustatek = "zustatek-kladny" if aktualni_zustatek >= 0 else "zustatek-zaporny"

        # Vytvoření zvýrazněné hlavičky pomocí CSS tříd
        st.markdown(
            f'<p class="ucet-nazev">'
            f'Pohyby účtu {ucet_k_zobrazeni} : {engine.get_ucet_nazev(ucet_k_zobrazeni)}'
            f'</p>'
            f'<p>Aktuální zůstatek: <span class="{css_class_zustatek}">{aktualni_zustatek:,.2f} Kč</span></p>',
            unsafe_allow_html=True
        )

        if pohyby:
            df_pohyby = pd.DataFrame(pohyby)

            # !!! ODSTRANĚNÍ SLOUPEČKU SMĚR ('Směr') !!!
            required_cols = ['Datum', 'Doklad Číslo', 'Popis Transakce', 'Částka']

            if 'Název Účtu' in df_pohyby.columns:
                required_cols.append('Název Účtu')

            # Filtrování sloupců (nyní bez 'Směr')
            df_pohyby = df_pohyby[required_cols]

            df_pohyby['Částka'] = df_pohyby['Částka'].apply(lambda x: f'{x:,.2f} Kč')

            st.dataframe(df_pohyby, width='stretch', hide_index=True)

        else:
            st.info(f"Na účtu {ucet_k_zobrazeni} nebyly nalezeny žádné pohyby.")


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
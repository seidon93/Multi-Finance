import sys
import os
from datetime import date
import streamlit as st
import pandas as pd

# Zajištění, že se importují moduly z nadřazeného adresáře (core)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dotenv import load_dotenv
from core.accounting_logic import AccountingEngine

load_dotenv()
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Předpokládáme, že ID klienta je prozatím 1
KLIENT_ID = 1

# Inicializace účetního enginu pro daného klienta (globálně)
engine = AccountingEngine(klient_id=KLIENT_ID)


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
        # --- HLAVIČKA TRANSAKCE (OPRAVENO A DOPLNĚNO) ---
        col1, col2 = st.columns(2)
        doklad_cislo = col1.text_input("Číslo Dokladu", value=f"FP-{KLIENT_ID}-")
        datum_transakce = col2.date_input("Datum Transakce", value=date.today())
        popis = st.text_area("Popis Transakce", placeholder="Popis účetní operace.")
        # -------------------------------------

        st.subheader("Účetní Pohyby Základu")

        # --- Pohyby Základu ---
        col_zaklad, col_protipolozka = st.columns(2)

        # Učty použité pro rozdělení základu a protipoložky (např. 511 a 321)
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

    # --- PŘEHLED ÚČTŮ: ZAHRNUTÍ VŠECH ANALYTICKÝCH ÚČTŮ S POHYBY ---
    sledovane_ucty = [
        '221', '311', '602', '511', '321',
        '343.1.21', '343.2.21', '343.1.12', '343.2.12', '343.1.00', '343.2.00',
        '343.1', '343.2'
    ]

    data = []
    for ucet in sledovane_ucty:
        # PŘEKLEP OPRAVEN: z get_zustaatek_uctu na get_zustatek_uctu
        zustatek = engine.get_zustatek_uctu(ucet)

        # DEFINOVÁNÍ A ZÍSKÁNÍ NÁZVU ÚČTU
        nazev = engine.get_ucet_nazev(ucet)

        # Zobrazíme jen účty s nenulovým zůstatkem NEBO klíčové syntetické účty
        if abs(zustatek) > 0.005 or ucet in ['221', '311', '321', '511', '602']:
            data.append({
                'Účet': ucet,
                'Název': nazev,
                'Zůstatek': zustatek
            })
    # Převedeme na DataFrame pro lepší formátování
    df = pd.DataFrame(data)
    df['Zůstatek'] = df['Zůstatek'].map('{:,.2f} Kč'.format)
    st.table(df)
    # ----------------------------------------------------

    # --- HISTORIE ÚČTU: ZOBRAZENÍ DETAILNÍCH POHYBŮ ---
    ucet_pro_detail = st.selectbox("Zobrazit detaily účtu", sorted(list(set(sledovane_ucty))))

    if st.button("Zobrazit Historii"):
        pohyby = engine.get_pohyby_uctu(ucet_pro_detail)

        st.subheader(f"Historie účtu {ucet_pro_detail} ({engine.get_ucet_nazev(ucet_pro_detail)})")

        if pohyby:
            # Konverze Listu Dictionarys na DataFrame
            df_pohyby = pd.DataFrame(pohyby)

            # Formátování a uspořádání sloupců pro přehlednost
            # Název Účtu by měl být zobrazen, pokud ho get_pohyby_uctu vrací
            if 'Název Účtu' in df_pohyby.columns:
                df_pohyby = df_pohyby[['Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka', 'Název Účtu']]
            else:
                df_pohyby = df_pohyby[['Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka']]

            df_pohyby['Částka'] = df_pohyby['Částka'].map('{:,.2f} Kč'.format)

            st.dataframe(df_pohyby, width='stretch')
        else:
            st.info("Na tomto účtu nejsou žádné pohyby.")
    # ----------------------------------------------------


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
            ucet_vstup = engine.get_dph_sazby()[sazba]['vstup']
            ucet_vystup = engine.get_dph_sazby()[sazba]['vystup']

            detail_data.append({
                'Sazba (%)': f"{sazba:.2f}",
                f'DPH VSTUP ({ucet_vstup})': data['vstup'],
                f'DPH VÝSTUP ({ucet_vystup})': data['vystup'],
                'Rozdíl DPH (Závazek - Pohledávka)': data['rozdil']
            })

        df_detail = pd.DataFrame(detail_data)

        # Formátování sloupců
        for col in df_detail.columns:
            if col not in ['Sazba (%)']:
                df_detail[col] = df_detail[col].map('{:,.2f} Kč'.format)

        st.dataframe(df_detail, width='stretch')

        st.markdown("---")

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
        st.write("Modul Historie...")

st.markdown("---")
st.subheader("📊 Aktuální Účetní Zůstatky (Agregace)")

# --- SEKCE PRO AGREGACI ZŮSTATKŮ ---
if st.button("Obnovit Zůstatky"):
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

        st.subheader("Syntetická Účetní Kniha")
        st.dataframe(zustatky_df, hide_index=True)
    else:
        st.warning("Nelze načíst nebo spočítat zůstatky. Zkontrolujte, zda je DB inicializována.")
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
        ("Nová Transakce", "Přehled Účtů", "Historie")
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
        # Logika v enginu určí, který z nich nese CELKEM a který ZÁKLAD.
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

    # Účty, které chceme sledovat (Rozšířeno o testovací účty)
    sledovane_ucty = ['221', '311', '602', '511', '343', '321', '343.1.21', '343.1.15',
                      '343.1.00']  # Doplněna analytika

    data = []
    for ucet in sledovane_ucty:
        zustatek = engine.get_zustatek_uctu(ucet)

        # --- KLÍČOVÝ KROK: DEFINOVÁNÍ NAZEV ---
        nazev = engine.get_ucet_nazev(ucet)
        # ---------------------------------------

        data.append({
            'Účet': ucet,
            'Název': nazev,
            'Zůstatek': zustatek
        })

    # Převedeme na DataFrame pro lepší formátování
    df = pd.DataFrame(data)
    df['Zůstatek'] = df['Zůstatek'].map('{:,.2f} Kč'.format)
    st.table(df)

    ucet_pro_detail = st.selectbox("Zobrazit detaily účtu", sledovane_ucty)
    if st.button("Zobrazit Historii"):
        pohyby = engine.get_pohyby_uctu(ucet_pro_detail)  # Nyní vrací Dicts

        st.subheader(f"Historie účtu {ucet_pro_detail} ({engine.get_ucet_nazev(ucet_pro_detail)})")

        if pohyby:
            # Původní kód musíme změnit, aby místo modelů Transakce použil Dictionary
            df_pohyby = pd.DataFrame(pohyby)  # <- Jednoduchá konverze listu Dictů

            # Formátování částky
            df_pohyby['Částka'] = df_pohyby['Částka'].map('{:,.2f} Kč'.format)

            # Zobrazení transakce jako DataFrame
            st.dataframe(df_pohyby, use_container_width=True)  # <- Použijte pandas DataFrame
        else:
            st.info("Na tomto účtu nejsou žádné pohyby.")


# --- Hlavní spouštěcí smyčka Streamlit ---
if __name__ == "__main__":
    modul = zobrazit_header()

    if modul == "Nová Transakce":
        formular_nova_transakce()
    elif modul == "Přehled Účtů":
        zobrazit_prehled_uctu()
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
        zustatky_df["Zůstatek"] = zustatky_df["Zůstatek"].map('{:,.2f} Kč'.format)

        st.subheader("Syntetická Účetní Kniha")
        st.dataframe(zustatky_df, hide_index=True)
    else:
        st.warning("Nelze načíst nebo spočítat zůstatky. Zkontrolujte, zda je DB inicializována.")
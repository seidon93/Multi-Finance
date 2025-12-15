import sys
import os

# Zajištění, že se importují moduly z nadřazeného adresáře (core)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dotenv import load_dotenv
import streamlit as st
import pandas as pd  # <-- PŘIDANÝ IMPORT pro práci s DataFrame

load_dotenv()
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# ... váš kód pro kontrolu
if not DB_PASSWORD:
    # V Streamlitu je lepší použít st.error a ukončit, než raise EnvironmentError
    pass

from datetime import date
from core.models import Transakce  # Tuto třídu již nebudeme pro ukládání potřebovat, ale ponecháme.
from core.accounting_logic import AccountingEngine

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
        # ... (doklad_cislo, datum, popis) ...

        st.subheader("Účetní Pohyby Základu")

        # --- Pohyby Základu ---
        col_zaklad, col_protipolozka = st.columns(2)

        # Zde vybíráme, který účet je účtem základu (např. 602) a který protipoložkou (např. 221/321)
        # Nyní jsou oba účty volitelné, a logika v enginu určí, který z nich ponese CELKEM a který ZÁKLAD.
        ucet_md_zaklad = col_zaklad.text_input("Účet MD (Základ / Celkem)", value="343")
        ucet_dal_zaklad = col_protipolozka.text_input("Účet D (Základ / Celkem)", value="321")
        castka_bez_dph = st.number_input("Částka ZÁKLADU (bez DPH)", min_value=0.01, format="%.2f")

        st.subheader("Nastavení DPH")

        # 1. Získání seznamu sazeb DPH
        dph_sazby_dict = engine.get_dph_sazby()
        dph_sazby_options = sorted(list(dph_sazby_dict.keys()), reverse=True)  # Sortujeme: 21.0, 15.0, 0.0

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
                # --- NOVÁ LOGIKA UKLÁDÁNÍ ---
                transakce_id = engine.save_transakce(
                    datum=datum_transakce,
                    popis=popis,
                    doklad_cislo=doklad_cislo,
                    ucet_md_zaklad=ucet_md_zaklad,
                    ucet_dal_zaklad=ucet_dal_zaklad,
                    castka_bez_dph=castka_bez_dph,  # Posíláme základ
                    sazba_dph=vybrana_sazba,
                    smer_dph_popis=smer_dph
                )

                if transakce_id:
                    st.success(f"Transakce {doklad_cislo} úspěšně uložena s ID {transakce_id}.")
                else:
                    st.error("Chyba při ukládání transakce. Zkontrolujte logy.")

            except Exception as e:
                st.exception(f"FATÁLNÍ CHYBA: {e}")

def zobrazit_prehled_uctu():
    """Zobrazí zůstatky vybraných účtů."""
    st.header("Přehled Zůstatků na Účtech")

    # Účty, které chceme sledovat (Rozšířeno o testovací účty)
    sledovane_ucty = ['221', '311', '602', '511', '343', '321']

    data = []
    for ucet in sledovane_ucty:
        # Voláme původní metodu z enginu, která nyní agreguje z UcetniPohyby
        zustatek = engine.get_zustaatek_uctu(ucet)
        data.append({
            'Účet': ucet,
            'Název (z rozvrhu)': "Není implementováno",
            'Zůstatek': zustatek
        })

    # Převedeme na DataFrame pro lepší formátování v Streamlitu
    df = pd.DataFrame(data)
    df['Zůstatek'] = df['Zůstatek'].map('{:,.2f} Kč'.format)
    st.table(df)

    ucet_pro_detail = st.selectbox("Zobrazit detaily účtu", sledovane_ucty)
    if st.button("Zobrazit Historii"):
        pohyby = engine.get_pohyby_uctu(ucet_pro_detail)
        st.subheader(f"Historie účtu {ucet_pro_detail}")

        if pohyby:
            # Zobrazení ve formátu tabulky
            tabulka_dat = [
                {
                    'Doklad ID': p.transakce_id,
                    'Směr': p.smer,
                    'Částka': p.castka,
                    # Nyní musíme dotáhnout datum a popis z Transakce na základě transakce_id
                } for p in pohyby
            ]
            st.dataframe(tabulka_dat)
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

# --- SEKCE PRO AGREGACI ZŮSTATKŮ (Ponechána pro rychlé testování) ---
if st.button("Obnovit Zůstatky"):

    # Kód je duplikován, ale volá stejný engine, jak je definován globálně.
    # Použijeme existující globální engine pro stabilitu.

    # 1. Spočítáme zůstatky
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
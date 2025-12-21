import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF


class FinancialPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        if hasattr(self, 'meta'):
            self.cell(0, 10, f"{self.meta['nazev_jednotky']} (IČO: {self.meta['ico_jednotky']})", ln=True)
            self.set_font('helvetica', '', 10)
            self.cell(0, 5, f"Sestaveno k: {self.meta['sestaveno_k']}", ln=True)
            self.cell(0, 5, f"Doklad č.: {self.meta['cislo_dokladu']}", ln=True)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Strana {self.page_no()}', align='C')


def generovat_pdf_vykazu(typ, cislo, metadata, df_polozky):
    pdf = FinancialPDF()
    pdf.meta = {**metadata, 'cislo_dokladu': cislo}
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, f"{typ.upper()}", ln=True, align='C')
    pdf.ln(5)

    pdf.set_font('helvetica', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    cols = [('Kód', 20), ('Položka', 100), ('EN', 30), ('Běžné', 40)]
    for col_name, width in cols:
        pdf.cell(width, 10, col_name, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('helvetica', '', 9)
    for _, row in df_polozky.iterrows():
        if row.get('Vyloučit'): continue
        zkratka = row.get('Zkratka')
        if zkratka in ['EBITDA', 'EBIT', 'EBT', 'EAT']:
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_fill_color(230, 240, 255)
        else:
            pdf.set_font('helvetica', '', 9)
            pdf.set_fill_color(255, 255, 255)

        hodnota = row.get('Běžné', 0)
        pdf.cell(20, 8, str(row.get('Kód', '-')), border=1, fill=True)
        pdf.cell(100, 8, str(row.get('Položka', '-')), border=1, fill=True)
        pdf.cell(30, 8, str(zkratka if zkratka and zkratka != "-" else "-"), border=1, fill=True)
        pdf.cell(40, 8, f"{float(hodnota if hodnota else 0):,.2f} Kč".replace(',', ' '), border=1, align='R', fill=True)
        pdf.ln()
    return pdf.output()


def zobrazit_ucetni_zaznamy(engine, KLIENT_ID, execute_query):
    klient_info = engine.get_klient_info()
    st.header("📂 Účetní záznamy a výkazy")

    with st.expander("📝 Nastavení hlavičky výkazu", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        nazev_firmy = c1.text_input("Účetní jednotka", value=klient_info['nazev'])
        ico_firmy = c2.text_input("IČO", value=klient_info['ico'])
        datum_k = c3.date_input("Sestaveno k dni", value=date.today())

        c4, c5 = st.columns(2)
        rok = c4.number_input("Rok", value=datetime.now().year)
        kvartal = c5.selectbox("Období", [None, 1, 2, 3, 4],
                               format_func=lambda x: "Celý rok" if x is None else f"{x}. kvartál")

    tab_r, tab_v, tab_cf, tab_arch = st.tabs(["⚖️ Rozvaha", "📈 Výsledovka", "💸 Cash Flow", "📁 Archiv"])

    with tab_r:
        if st.button("✨ Generovat data pro Rozvahu", use_container_width=True):
            data_a = engine.get_vykaz_podklady(rok, kvartal, "Rozvaha_Aktiva")
            data_p = engine.get_vykaz_podklady(rok, kvartal, "Rozvaha_Pasiva")

            st.session_state['draft_rozvaha_a'] = pd.DataFrame(data_a if data_a else [],
                                                               columns=["Kód", "Položka", "Běžné"])
            st.session_state['draft_rozvaha_p'] = pd.DataFrame(data_p if data_p else [],
                                                               columns=["Kód", "Položka", "Běžné"])
            st.session_state['draft_rozvaha_a']['Vyloučit'] = False
            st.session_state['draft_rozvaha_p']['Vyloučit'] = False

        if 'draft_rozvaha_a' in st.session_state:
            st.divider()
            sekce_r = st.segmented_control("Vyberte část výkazu:", options=["🟢 AKTIVA", "🔴 PASIVA"], default="🟢 AKTIVA")

            if sekce_r == "🟢 AKTIVA":
                st.subheader("Aktiva (Majetek)")
                st.session_state['draft_rozvaha_a'] = st.data_editor(st.session_state['draft_rozvaha_a'],
                                                                     num_rows="dynamic", key="ed_roz_a",
                                                                     use_container_width=True)
            else:
                st.subheader("Pasiva (Zdroje)")
                df_p_view = st.session_state['draft_rozvaha_p'].copy()
                df_p_view['Běžné'] = df_p_view['Běžné'].apply(lambda x: abs(x) if x is not None else 0)
                st.session_state['draft_rozvaha_p'] = st.data_editor(df_p_view, num_rows="dynamic", key="ed_roz_p",
                                                                     use_container_width=True)

            # Kontrola bilanční rovnosti
            sum_a = st.session_state['draft_rozvaha_a']['Běžné'].sum()
            sum_p = st.session_state['draft_rozvaha_p']['Běžné'].abs().sum()
            rozdil = round(sum_a - sum_p, 2)

            c1, c2, c3 = st.columns(3)
            c1.metric("Aktiva celkem", f"{sum_a:,.2f} Kč".replace(',', ' '))
            c2.metric("Pasiva celkem", f"{sum_p:,.2f} Kč".replace(',', ' '))
            if rozdil == 0:
                c3.success("⚖️ Vyrovnáno")
            else:
                c3.error(f"⚠️ Rozdíl: {rozdil:,.2f} Kč")

            if st.button("💾 Archivovat kompletní Rozvahu", type="primary", use_container_width=True):
                komplet = pd.concat([st.session_state['draft_rozvaha_a'], st.session_state['draft_rozvaha_p']])
                meta = {'sestaveno_k': datum_k, 'nazev_jednotky': nazev_firmy, 'ico_jednotky': ico_firmy}
                if engine.ulozit_vykaz_do_archivu("Rozvaha", rok, kvartal, komplet, meta):
                    st.success("Rozvaha uložena.")

    with tab_v:
        if st.button("✨ Generovat Výsledovku", use_container_width=True):
            data = engine.get_vykaz_podklady(rok, kvartal, "Vysledovka")
            if data:
                df_v = pd.DataFrame(data, columns=["Kód", "Položka", "Běžné"])
                df_v['Zkratka'] = "-"
                df_v['Vyloučit'] = False
                st.session_state['draft_vysledovka'] = df_v

        if 'draft_vysledovka' in st.session_state:
            st.session_state['draft_vysledovka'] = st.data_editor(st.session_state['draft_vysledovka'],
                                                                  num_rows="dynamic", use_container_width=True,
                                                                  key="ed_vys_editor",
                                                                  column_config={
                                                                      "Zkratka": st.column_config.SelectboxColumn(
                                                                          "Zkratka (EN)",
                                                                          options=["EBITDA", "EBIT", "EBT", "EAT",
                                                                                   "REVENUE", "COGS", "-"])})
            if st.button("💾 Archivovat Výsledovku", type="primary", use_container_width=True):
                meta = {'sestaveno_k': datum_k, 'nazev_jednotky': nazev_firmy, 'ico_jednotky': ico_firmy}
                engine.ulozit_vykaz_do_archivu("Vysledovka", rok, kvartal, st.session_state['draft_vysledovka'], meta)
                st.success("Výsledovka uložena.")

    with tab_cf:
        if st.button("✨ Generovat návrh CF", use_container_width=True):
            data = engine.get_vykaz_podklady(rok, kvartal, "CF")
            if data:
                st.session_state['draft_cf'] = pd.DataFrame(data, columns=["Kód", "Položka", "Běžné"])
                st.session_state['draft_cf']['Vyloučit'] = False

        if 'draft_cf' in st.session_state:
            st.session_state['draft_cf'] = st.data_editor(st.session_state['draft_cf'], num_rows="dynamic",
                                                          key="ed_cf_editor", use_container_width=True)
            if st.button("💾 Archivovat Cash Flow", type="primary", use_container_width=True):
                meta = {'sestaveno_k': datum_k, 'nazev_jednotky': nazev_firmy, 'ico_jednotky': ico_firmy}
                engine.ulozit_vykaz_do_archivu("CF", rok, kvartal, st.session_state['draft_cf'], meta)
                st.success("Cash Flow uloženo.")

    with tab_arch:
        zobrazit_archiv_vykazu(engine, KLIENT_ID, execute_query)


def zobrazit_archiv_vykazu(engine, KLIENT_ID, execute_query):
    st.subheader("📁 Archiv vygenerovaných výkazů")

    # Filtry pro vyhledávání
    c1, c2 = st.columns(2)
    search_rok = c1.number_input("Rok", value=datetime.now().year, key="arch_rok_filter")
    search_typ = c2.selectbox("Typ výkazu", ["Vše", "Rozvaha", "Výsledovka", "CF"], key="arch_typ_filter")

    # SQL dotaz načítá i název jednotky uložený v době archivace
    sql_arch = """
        SELECT id, cislo_dokladu, typ_vykazu, rok, kvartal, datum_vytvoreni, nazev_jednotky 
        FROM VykazyArchiv 
        WHERE klient_id = ? AND rok = ?
    """
    params = [KLIENT_ID, search_rok]
    if search_typ != "Vše":
        sql_arch += " AND typ_vykazu = ?"
        params.append(search_typ)
    sql_arch += " ORDER BY datum_vytvoreni DESC"

    arch_data = execute_query(sql_arch, tuple(params))

    if not arch_data:
        st.info("V archivu nejsou žádné záznamy pro tohoto klienta.")
        return

    # Převod pyodbc.Row na list pro zpracování v Pandas
    df_arch = pd.DataFrame(
        [list(row) for row in arch_data],
        columns=["ID", "Číslo dokladu", "Typ", "Rok", "Kvartál", "Vytvořeno", "Účetní jednotka"]
    )

    # Zobrazení tabulky s on_select="rerun" pro interaktivitu
    selected_row = st.dataframe(
        df_arch,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if selected_row and len(selected_row.selection.rows) > 0:
        idx = selected_row.selection.rows[0]
        v_id = df_arch.iloc[idx]["ID"]
        v_typ = df_arch.iloc[idx]["Typ"]
        v_cislo = df_arch.iloc[idx]["Číslo dokladu"]
        # Načtení názvu firmy přímo z řádku archivu
        v_firma = df_arch.iloc[idx]["Účetní jednotka"]
        v_datum = df_arch.iloc[idx]["Vytvořeno"]

        st.divider()
        st.subheader(f"📄 Detail: {v_cislo}")

        # Načtení položek výkazu
        sql_items = "SELECT kod_polozky, nazev_polozky, zkratka_en, castka_bezne, is_vylouceno FROM VykazyPolozky WHERE vykaz_id = ? ORDER BY id ASC"
        items_raw = execute_query(sql_items, (v_id,))

        if items_raw:
            df_items = pd.DataFrame([list(r) for r in items_raw],
                                    columns=["Kód", "Položka", "Zkratka", "Běžné", "Vyloučit"])
            ed_items = st.data_editor(df_items, num_rows="dynamic", use_container_width=True, key=f"edit_arch_{v_id}")

            c_save, c_pdf, c_del = st.columns(3)

            if c_save.button("💾 Uložit změny", use_container_width=True):
                for _, row in ed_items.iterrows():
                    execute_query(
                        "UPDATE VykazyPolozky SET nazev_polozky=?, zkratka_en=?, castka_bezne=?, is_vylouceno=? WHERE vykaz_id=? AND kod_polozky=?",
                        (row['Položka'], row['Zkratka'], row['Běžné'], 1 if row['Vyloučit'] else 0, v_id, row['Kód'])
                    )
                st.success("Změny uloženy.")

            if c_pdf.button("🖨️ Export PDF", use_container_width=True):
                # ZDE SE DĚJE DYNAMICKÉ NAČTENÍ INFO O KLIENTOVI
                klient_info = engine.get_klient_info()

                metadata = {
                    'nazev_jednotky': v_firma,  # Název z doby uložení
                    'ico_jednotky': klient_info['ico'],  # Aktuální IČO z tabulky Klienti
                    'sestaveno_k': v_datum.strftime('%d.%m.%Y') if isinstance(v_datum, datetime) else str(v_datum)
                }
                pdf_out = generovat_pdf_vykazu(v_typ, v_cislo, metadata, ed_items)
                st.download_button("📥 STÁHNOUT PDF", pdf_out, f"{v_cislo}.pdf", "application/pdf")

            if c_del.button("🗑️ Smazat", type="secondary", use_container_width=True):
                execute_query("DELETE FROM VykazyArchiv WHERE id = ?", (v_id,))
                st.rerun()
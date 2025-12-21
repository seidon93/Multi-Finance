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

    # Titulek výkazu
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, f"{typ.upper()}", ln=True, align='C')
    pdf.ln(5)

    # Hlavička tabulky
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    cols = [('Kód', 20), ('Položka', 100), ('EN', 30), ('Běžné', 40)]
    for col_name, width in cols:
        pdf.cell(width, 10, col_name, border=1, align='C', fill=True)
    pdf.ln()

    # Data
    pdf.set_font('helvetica', '', 9)
    for _, row in df_polozky.iterrows():
        # 1. Kontrola vyloučení
        if row.get('Vyloučit'):
            continue

        # 2. Logika zvýraznění (EBITDA, EBIT...)
        zkratka = row.get('Zkratka')
        if zkratka in ['EBITDA', 'EBIT', 'EBT', 'EAT']:
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_fill_color(230, 240, 255)  # Lehce modré podbarvení
        else:
            pdf.set_font('helvetica', '', 9)
            pdf.set_fill_color(255, 255, 255)

        # 3. Ošetření None hodnot u částek
        hodnota = row.get('Běžné', 0)
        if hodnota is None:
            hodnota = 0

        # 4. Vykreslení buněk řádku
        pdf.cell(20, 8, str(row.get('Kód', '-')), border=1, fill=True)
        pdf.cell(100, 8, str(row.get('Položka', '-')), border=1, fill=True)
        pdf.cell(30, 8, str(zkratka if zkratka and zkratka != "-" else "-"), border=1, fill=True)

        # Formátování: 1 234 567.89 Kč
        formatovana_castka = f"{float(hodnota):,.2f}".replace(',', ' ')
        pdf.cell(40, 8, f"{formatovana_castka} Kč", border=1, align='R', fill=True)
        pdf.ln()

    return pdf.output()

def zobrazit_ucetni_zaznamy(engine, KLIENT_ID, execute_query):
    st.header("📂 Účetní záznamy a výkazy")

    # --- DYNAMICKÁ HLAVIČKA ---
    with st.expander("📝 Nastavení hlavičky výkazu", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        nazev_firmy = c1.text_input("Účetní jednotka", value="Vzorová firma s.r.o.")
        ico_firmy = c2.text_input("IČO", value="12345678")
        datum_k = c3.date_input("Sestaveno k dni", value=date.today())

        c4, c5 = st.columns(2)
        rok = c4.number_input("Rok", value=2025)
        kvartal = c5.selectbox("Období", [None, 1, 2, 3, 4],
                               format_func=lambda x: "Celý rok" if x is None else f"{x}. kvartál")

    tab_r, tab_v, tab_arch = st.tabs(["⚖️ Rozvaha", "📈 Výsledovka", "📁 Archiv"])

    with tab_r:
        if st.button("🔍 Generovat Rozvahu"):
            data = engine.get_vykaz_podklady(rok, kvartal, "Rozvaha")
            st.session_state['draft_rozvaha'] = pd.DataFrame(data, columns=["Kód", "Položka", "Běžné"])
            st.session_state['draft_rozvaha']['Vyloučit'] = False

        if 'draft_rozvaha' in st.session_state:
            edited_a = st.data_editor(st.session_state['draft_rozvaha'], num_rows="dynamic", key="ed_roz_a")
            if st.button("💾 Archivovat Rozvahu", type="primary"):
                meta = {'sestaveno_k': datum_k, 'nazev_jednotky': nazev_firmy, 'ico_jednotky': ico_firmy}
                if engine.ulozit_vykaz_do_archivu("Rozvaha", rok, kvartal, edited_a, meta):
                    st.success("Rozvaha uložena.")

    with tab_v:
        if st.button("🔍 Generovat Výsledovku"):
            data = engine.get_vykaz_podklady(rok, kvartal, "Vysledovka")
            st.session_state['draft_vysledovka'] = pd.DataFrame(data, columns=["Kód", "Položka", "Běžné"])
            st.session_state['draft_vysledovka']['Zkratka'] = "-"
            st.session_state['draft_vysledovka']['Vyloučit'] = False

        if 'draft_vysledovka' in st.session_state:
            edited_v = st.data_editor(
                st.session_state['draft_vysledovka'],
                num_rows="dynamic",
                column_config={"Zkratka": st.column_config.SelectboxColumn("Zkratka (EN)", options=["EBITDA", "EBIT", "EBT", "EAT", "REVENUE", "COGS", "-"])}
            )
            if st.button("💾 Archivovat Výsledovku", type="primary"):
                meta = {'sestaveno_k': datum_k, 'nazev_jednotky': nazev_firmy, 'ico_jednotky': ico_firmy}
                if engine.ulozit_vykaz_do_archivu("Vysledovka", rok, kvartal, edited_v, meta):
                    st.success("Výsledovka uložena.")

    with tab_arch:
        zobrazit_archiv_vykazu(engine, KLIENT_ID, execute_query)

def zobrazit_archiv_vykazu(engine, KLIENT_ID, execute_query):
    st.subheader("📁 Archiv vygenerovaných výkazů")

    # 1. Filtry pro vyhledávání
    c1, c2 = st.columns(2)
    search_rok = c1.number_input("Rok", value=datetime.now().year, key="arch_rok_filter")
    search_typ = c2.selectbox("Typ výkazu", ["Vše", "Rozvaha", "Výsledovka"], key="arch_typ_filter")

    # 2. Definice SQL dotazu (přesně 7 sloupců)
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

    # Spuštění dotazu skrze engine
    arch_data = execute_query(sql_arch, tuple(params))

    # 3. Kontrola dat před vytvořením DataFrame (Obrana proti chybě Shape)
    if not arch_data or not isinstance(arch_data, list):
        st.info("V archivu nebyly nalezeny žádné záznamy pro vybrané období.")
        return

    # Pokud execute_query vrátí chybu jako string v listu, zachytíme to zde
    if len(arch_data) > 0 and not isinstance(arch_data[0], (list, tuple)):
        st.error(f"Chyba databáze: Neočekávaný formát dat. Server vrátil: {arch_data[0]}")
        return

    # Kontrola počtu sloupců (musí být 7)
    if len(arch_data) > 0 and len(arch_data[0]) != 7:
        st.error(f"Nesoulad dat: SQL vrátilo {len(arch_data[0])} sloupců, ale rozhraní očekává 7. Prověřte strukturu tabulky VykazyArchiv.")
        return

    # 4. Tvorba DataFrame
    df_arch = pd.DataFrame(
        arch_data,
        columns=["ID", "Číslo dokladu", "Typ", "Rok", "Kvartál", "Vytvořeno", "Účetní jednotka"]
    )

    # 5. Zobrazení tabulky s výběrem
    st.markdown("### Seznam uložených dokumentů")
    selected_row = st.dataframe(
        df_arch,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single"
    )

    # --- 6. DETAIL VYBRANÉHO VÝKAZU ---
    if selected_row and len(selected_row.selection.indices) > 0:
        idx = selected_row.selection.indices[0]
        v_id = df_arch.iloc[idx]["ID"]
        v_typ = df_arch.iloc[idx]["Typ"]
        v_cislo = df_arch.iloc[idx]["Číslo dokladu"]

        st.divider()
        st.subheader(f"📄 Detail výkazu: {v_cislo}")

        # Načtení položek konkrétního výkazu
        sql_items = """
            SELECT kod_polozky, nazev_polozky, zkratka_en, castka_bezne, is_vylouceno 
            FROM VykazyPolozky 
            WHERE vykaz_id = ? 
            ORDER BY id ASC
        """
        items_data = execute_query(sql_items, (v_id,))

        if items_data:
            df_items = pd.DataFrame(items_data, columns=["Kód", "Položka", "Zkratka", "Běžné", "Vyloučit"])

            st.info("Zde můžete upravit hodnoty nebo zkratky a změny znovu uložit.")
            ed_items = st.data_editor(
                df_items,
                num_rows="dynamic",
                use_container_width=True,
                key=f"edit_arch_{v_id}",
                column_config={
                    "Zkratka": st.column_config.SelectboxColumn("Zkratka (EN)", options=["EBITDA", "EBIT", "EBT", "EAT", "REVENUE", "COGS", "-"]),
                    "Vyloučit": st.column_config.CheckboxColumn("Vyloučit")
                }
            )

            # --- 7. AKCE (Uložit, PDF, Smazat) ---
            c_save, c_pdf, c_del = st.columns(3)

            if c_save.button("💾 Uložit změny", use_container_width=True):
                for _, row in ed_items.iterrows():
                    execute_query(
                        "UPDATE VykazyPolozky SET nazev_polozky=?, zkratka_en=?, castka_bezne=?, is_vylouceno=? WHERE vykaz_id=? AND kod_polozky=?",
                        (row['Položka'], row['Zkratka'], row['Běžné'], 1 if row['Vyloučit'] else 0, v_id, row['Kód'])
                    )
                st.success("Změny byly v archivu aktualizovány.")

            if c_pdf.button("🖨️ Exportovat PDF", use_container_width=True):
                # Metadata pro PDF
                metadata = {
                    'nazev_jednotky': df_arch.iloc[idx]["Účetní jednotka"],
                    'ico_jednotky': "12345678", # Zde můžete vytáhnout reálné IČO z DB
                    'sestaveno_k': df_arch.iloc[idx]["Vytvořeno"].strftime('%d.%m.%Y')
                }
                pdf_out = generovat_pdf_vykazu(v_typ, v_cislo, metadata, ed_items)
                st.download_button("📥 STÁHNOUT PDF", pdf_out, f"{v_cislo}.pdf", "application/pdf")

            if c_del.button("🗑️ Smazat z archivu", type="secondary", use_container_width=True):
                execute_query("DELETE FROM VykazyArchiv WHERE id = ?", (v_id,))
                st.warning("Výkaz byl odstraněn.")
                st.rerun()
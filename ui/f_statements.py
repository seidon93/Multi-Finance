import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF


# --- PDF GENERÁTOR ---
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


# --- HLAVNÍ FUNKCE ÚČETNICTVÍ ---

import streamlit as st
import pandas as pd
from datetime import date, datetime


def zobrazit_ucetni_zaznamy(engine, KLIENT_ID, execute_query):
    # 1. Načtení informací o klientovi pro hlavičku
    klient_info = engine.get_klient_info(KLIENT_ID)
    st.header(f"📂 Účetní výkazy pro: {klient_info['nazev']}")

    # Pomocná funkce pro bezpečné získání hodnoty z konkrétního řádku (prevence NaN)
    def get_val_by_r(df, r_code, col='Netto'):
        if df is None or df.empty: return 0.0
        val = df[df['Číslo řádku'] == r_code][col].values
        if len(val) > 0 and pd.notnull(val[0]):
            return float(val[0])
        return 0.0

    with st.expander("📝 Nastavení hlavičky výkazu", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        nazev_firmy = c1.text_input("Účetní jednotka", value=klient_info['nazev'])
        ico_firmy = c2.text_input("IČO", value=klient_info['ico'])
        datum_k = c3.date_input("Sestaveno k dni", value=date.today())
        rok = st.number_input("Rok", value=datetime.now().year)
        kvartal = st.selectbox("Období", [None, 1, 2, 3, 4],
                               format_func=lambda x: "Celý rok" if x is None else f"{x}. kvartál")

    tab_r, tab_v, tab_cf, tab_arch = st.tabs(["⚖️ Rozvaha", "📈 Výsledovka", "💸 Cash Flow", "📁 Archiv"])

    # Styl pro profesionální zvýraznění řádků
    def style_header(row):
        if row.get('is_bold'):
            return ['background-color: #1a1c23; color: white; font-weight: bold'] * len(row)
        return [''] * len(row)

    # --- ⚖️ ROZVAHA ---
    with tab_r:
        if st.button("✨ Generovat data pro Rozvahu", use_container_width=True):
            st.session_state['draft_rozvaha_a'] = pd.DataFrame(
                engine.get_vykaz_podklady(KLIENT_ID, datum_k, "Rozvaha_Aktiva"))
            st.session_state['draft_rozvaha_p'] = pd.DataFrame(
                engine.get_vykaz_podklady(KLIENT_ID, datum_k, "Rozvaha_Pasiva"))
            st.rerun()

        if 'draft_rozvaha_a' in st.session_state:
            sekce_r = st.segmented_control("Vyberte část výkazu:", options=["🟢 AKTIVA", "🔴 PASIVA"], default="🟢 AKTIVA")

            # Načtení dat podle vybrané sekce
            is_aktiva = (sekce_r == "🟢 AKTIVA")
            source_df = st.session_state['draft_rozvaha_a'] if is_aktiva else st.session_state['draft_rozvaha_p']

            # VIZUÁLNÍ ÚPRAVA: Pro nadpisy (bold) vymažeme čísla
            df_view = source_df.copy()
            cols_to_clear = ["Brutto", "Korekce", "Netto", "Minulé období", "Zdroj"]
            df_view.loc[df_view['is_bold'] == True, [c for c in cols_to_clear if c in df_view.columns]] = None

            st.subheader(f"{'Aktiva (Majetek)' if is_aktiva else 'Pasiva (Zdroje)'} - Plný rozsah")
            st.data_editor(df_view.style.apply(style_header, axis=1), hide_index=True, use_container_width=True,
                           column_config={"is_bold": None, "Brutto": st.column_config.NumberColumn(format="%.2f"),
                                          "Netto": st.column_config.NumberColumn(format="%.2f")},
                           disabled=["Označení", "Číslo řádku", "POLOŽKA"], key=f"ed_roz_{sekce_r}_final")

            # --- FIX NaN: Načtení celků přímo z řádků 01 ---
            sum_a = get_val_by_r(st.session_state['draft_rozvaha_a'], '01', 'Netto')
            sum_p = get_val_by_r(st.session_state['draft_rozvaha_p'], '01', 'Brutto')
            rozdil = round(sum_a - sum_p, 2)

            c1, c2, c3 = st.columns(3)
            c1.metric("Aktiva celkem", f"{sum_a:,.2f} Kč".replace(',', ' '))
            c2.metric("Pasiva celkem", f"{sum_p:,.2f} Kč".replace(',', ' '))
            if abs(rozdil) < 0.01:
                st.success("⚖️ Vyrovnáno")
            else:
                st.error(f"⚠️ Rozdíl: {rozdil:,.2f} Kč")

    # --- 📈 VÝSLEDOVKA ---
    with tab_v:
        if st.button("✨ Generovat Výsledovku", use_container_width=True):
            st.session_state['draft_vysledovka'] = pd.DataFrame(
                engine.get_vykaz_podklady(KLIENT_ID, datum_k, "Vysledovka"))
            st.rerun()

        if 'draft_vysledovka' in st.session_state:
            raw_v = st.session_state['draft_vysledovka']

            # Banner pro Obchodní marži (načteno z řádku 02 a 04)
            obchodni_marze = get_val_by_r(raw_v, '02', 'Brutto') + get_val_by_r(raw_v, '04', 'Brutto')
            st.info(f"📊 **Obchodní marže (II. - A.1.):** {obchodni_marze:,.2f} Kč".replace(',', ' '))

            # Vizuální úprava výsledovky (vyčištění nadpisů)
            df_v_view = raw_v.copy()
            df_v_view.loc[df_v_view['is_bold'] == True, ["Brutto", "Netto", "Minulé období", "Zdroj"]] = None

            st.data_editor(df_v_view.style.apply(style_header, axis=1),
                           column_config={"is_bold": None,
                                          "Brutto": st.column_config.NumberColumn("Běžné", format="%.2f"),
                                          "Minulé období": st.column_config.NumberColumn("Minulé", format="%.2f"),
                                          "Netto": None},
                           disabled=["Označení", "Číslo řádku", "POLOŽKA"],
                           hide_index=True, use_container_width=True, key="ed_vys_final_v7")

            # --- FIX NaN: Načtení výsledku hospodaření z řádku 55 ---
            vh_konecny = get_val_by_r(raw_v, '55', 'Brutto')
            st.metric("Výsledek hospodaření za účetní období (***)", f"{vh_konecny:,.2f} Kč".replace(',', ' '))

    # --- 💸 CASH FLOW ---
    with tab_cf:
        if st.button("✨ Generovat návrh CF", use_container_width=True):
            st.session_state['draft_cf'] = pd.DataFrame(engine.get_vykaz_podklady(KLIENT_ID, datum_k, "CF"))
            st.rerun()

        if 'draft_cf' in st.session_state:
            raw_cf = st.session_state['draft_cf']

            # Bezpečné načtení finální změny stavu (řádek F)
            cista_zmena = get_val_by_r(raw_cf, 'F', 'Brutto')

            st.info(f"🌊 **Čistý tok hotovosti za období:** {cista_zmena:,.2f} Kč".replace(',', ' '))

            # Vizuální úprava (vyčištění nadpisů pro tmavý design přes celou šířku)
            df_cf_view = raw_cf.copy()
            # Ponecháme čísla jen u klíčových součtových řádků a datových řádků
            df_cf_view.loc[
                (df_cf_view['is_bold'] == True) & (~df_cf_view['Číslo řádku'].isin(['P0', 'R', 'F', 'A_CELKEM'])),
                ["Brutto", "Netto", "Minulé období"]] = None

            st.data_editor(
                df_cf_view.style.apply(style_header, axis=1),
                column_config={
                    "is_bold": None,
                    "Brutto": st.column_config.NumberColumn("Částka", format="%.2f"),
                    "Minulé období": st.column_config.NumberColumn("Minulé", format="%.2f"),
                    "Netto": None
                },
                disabled=["Označení", "Číslo řádku", "POLOŽKA"],
                hide_index=True, use_container_width=True, key="ed_cf_final_v8"
            )

            # Finální metrika: Stav peněz na konci (řádek R)
            stav_koncovy = get_val_by_r(raw_cf, 'R', 'Brutto')
            st.metric("Disponibilní hotovost k rozvahovému dni (R.)", f"{stav_koncovy:,.2f} Kč".replace(',', ' '))


# --- ARCHIV FUNKCE ---
def zobrazit_archiv_vykazu(engine, KLIENT_ID, execute_query):
    st.subheader("📁 Archiv vygenerovaných výkazů")
    c1, c2 = st.columns(2)
    search_rok = c1.number_input("Rok", value=datetime.now().year, key="arch_rok_filter")
    search_typ = c2.selectbox("Typ výkazu", ["Vše", "Rozvaha", "Výsledovka", "CF"], key="arch_typ_filter")

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
        st.info("V archivu nejsou žádné záznamy.")
        return

    df_arch = pd.DataFrame([list(row) for row in arch_data],
                           columns=["ID", "Číslo dokladu", "Typ", "Rok", "Kvartál", "Vytvořeno", "Účetní jednotka"])
    selected_row = st.dataframe(df_arch, width="content", hide_index=True, on_select="rerun",
                                selection_mode="single-row")

    if selected_row and len(selected_row.selection.rows) > 0:
        idx = selected_row.selection.rows[0]
        row_data = df_arch.iloc[idx]
        v_id, v_typ, v_cislo, v_firma, v_datum = row_data["ID"], row_data["Typ"], row_data["Číslo dokladu"], row_data[
            "Účetní jednotka"], row_data["Vytvořeno"]

        st.divider()
        st.subheader(f"📄 Detail: {v_cislo}")

        sql_items = "SELECT kod_polozky, nazev_polozky, zkratka_en, castka_bezne, is_vylouceno FROM VykazyPolozky WHERE vykaz_id = ? ORDER BY id ASC"
        items_raw = execute_query(sql_items, (v_id,))

        if items_raw:
            df_items = pd.DataFrame([list(r) for r in items_raw],
                                    columns=["Kód", "Položka", "Zkratka", "Běžné", "Vyloučit"])
            # OPRAVA: data_editor potřebuje konfiguraci, aby Vyloučit byl checkbox
            ed_items = st.data_editor(df_items, num_rows="dynamic", width="content", key=f"edit_arch_{v_id}",
                                      column_config={"Vyloučit": st.column_config.CheckboxColumn("Vyloučit")})

            c_save, c_pdf, c_del = st.columns(3)
            if c_save.button("💾 Uložit změny", width="content"):
                for _, row in ed_items.iterrows():
                    execute_query(
                        "UPDATE VykazyPolozky SET nazev_polozky=?, zkratka_en=?, castka_bezne=?, is_vylouceno=? WHERE vykaz_id=? AND kod_polozky=?",
                        (row['Položka'], row['Zkratka'], row['Běžné'], 1 if row['Vyloučit'] else 0, v_id, row['Kód'])
                    )
                st.success("Změny uloženy.")

            if c_pdf.button("🖨️ Export PDF", width="content"):
                # OPRAVA: Načtení aktuálního IČO pro PDF
                klient_info = engine.get_klient_info()
                metadata = {
                    'nazev_jednotky': v_firma,
                    'ico_jednotky': klient_info['ico'],
                    'sestaveno_k': v_datum.strftime('%d.%m.%Y') if isinstance(v_datum, datetime) else str(v_datum)
                }
                pdf_out = generovat_pdf_vykazu(v_typ, v_cislo, metadata, ed_items)
                st.download_button("📥 STÁHNOUT PDF", pdf_out, f"{v_cislo}.pdf", "application/pdf")

            if c_del.button("🗑️ Smazat", type="secondary", width="content"):
                execute_query("DELETE FROM VykazyArchiv WHERE id = ?", (v_id,))
                st.rerun()
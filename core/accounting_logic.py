from collections import defaultdict
from core.database import execute_query, Database
from core.models import UcetniPohyb
from decimal import Decimal
import pandas as pd


class AccountingEngine:
    """Třída pro výpočet účetních dat a reportů."""

    def __init__(self, klient_id):
        self.klient_id = klient_id
        self.zkontroluj_a_oprav_db()

    def zkontroluj_a_oprav_db(self):
        """
        Pomocná metoda: Zkontroluje, zda existuje sloupec 'datum_uzaverky'.
        Pokud ne, automaticky ho přidá.
        """
        check_sql = "SELECT col_length('Klienti', 'datum_uzaverky')"
        try:
            res = execute_query(check_sql)
            # Pokud col_length vrátí None, sloupec neexistuje
            if not res or res[0][0] is None:
                print("⚠️ Sloupec 'datum_uzaverky' chybí. Přidávám ho...")
                alter_sql = "ALTER TABLE Klienti ADD datum_uzaverky DATE NULL;"

                with Database() as conn:
                    cursor = conn.cursor()
                    cursor.execute(alter_sql)
                    conn.commit()
                print("✅ Databáze úspěšně aktualizována.")
        except Exception as e:
            print(f"Chyba při kontrole/opravě DB: {e}")

        audit_sql = """
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLog' AND xtype='U')
                CREATE TABLE AuditLog (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    transakce_id INT,
                    datum_zmeny DATETIME DEFAULT GETDATE(),
                    typ_akce NVARCHAR(50), -- 'EDIT', 'DELETE'
                    puvodni_data NVARCHAR(MAX), -- Uložíme sem starý stav jako text/JSON
                    novy_data NVARCHAR(MAX) -- Uložíme sem nový stav
                );
                """
        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(audit_sql)
                conn.commit()
        except Exception as e:
            print(f"Chyba při vytváření AuditLog: {e}")

    def get_transakce_detail(self, transakce_id):
        """Vrátí kompletní info o transakci včetně účtů pro editaci."""
        sql = """
            SELECT T.datum, T.doklad_cislo, T.popis, 
                   P.ucet, P.smer, P.castka
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.id = ?
        """
        try:
            results = execute_query(sql, (transakce_id,))
            if not results:
                return None

            # Hlavička je stejná pro všechny řádky
            hlavicka = {
                'id': transakce_id,
                'datum': results[0][0],
                'doklad': results[0][1],
                'popis': results[0][2],
                'pohyby': []
            }

            # Rozparsujeme pohyby, abychom našli MD, D a DPH
            # Toto je zjednodušená logika pro zobrazení v editoru
            for row in results:
                hlavicka['pohyby'].append({
                    'ucet': row[3],
                    'smer': row[4],
                    'castka': float(row[5])
                })

            return hlavicka
        except Exception as e:
            print(f"Chyba detailu transakce: {e}")
            return None

    def upravit_transakci(self, transakce_id, nove_datum, novy_popis, novy_doklad,
                          ucet_md, ucet_dal, castka, sazba_dph, smer_dph_popis):
        """
        Provede bezpečnou editaci:
        1. Zkontroluje uzávěrku (pro staré i nové datum).
        2. Uloží starý stav do AuditLog.
        3. Aktualizuje hlavičku.
        4. Smaže staré pohyby a vytvoří nové (nejčistší cesta).
        """

        # 1. Načteme starý stav (pro log a kontrolu data)
        stary_stav = self.get_transakce_detail(transakce_id)
        if not stary_stav:
            raise ValueError("Transakce neexistuje.")

        # 2. Kontrola uzávěrky (Musí být otevřeno pro STARÉ i NOVÉ datum)
        # Pokud měním datum z prosince na leden, musí být otevřený i prosinec!
        self.zkontroluj_zda_je_otevreno(stary_stav['datum'])
        self.zkontroluj_zda_je_otevreno(nove_datum)

        # 3. Příprava popisu pro AuditLog (zjednodušený string)
        log_old = f"Datum: {stary_stav['datum']}, Doklad: {stary_stav['doklad']}, Částka: {stary_stav['pohyby'][0]['castka']}"
        log_new = f"Datum: {nove_datum}, Doklad: {novy_doklad}, Částka: {castka}"

        # 4. SQL Operace (v jedné transakci)
        try:
            with Database() as conn:
                cursor = conn.cursor()

                # A) Zápis do AuditLog
                cursor.execute("""
                    INSERT INTO AuditLog (transakce_id, typ_akce, puvodni_data, novy_data)
                    VALUES (?, 'EDIT', ?, ?)
                """, (transakce_id, log_old, log_new))

                # B) Update hlavičky
                cursor.execute("""
                    UPDATE Transakce 
                    SET datum = ?, popis = ?, doklad_cislo = ?
                    WHERE id = ?
                """, (nove_datum, novy_popis, novy_doklad, transakce_id))

                # C) Smazání starých pohybů (nejjednodušší způsob jak přepsat účty/částky)
                cursor.execute("DELETE FROM UcetniPohyby WHERE transakce_id = ?", (transakce_id,))

                # D) Výpočet nových částek (Stejná logika jako v save_transakce)
                castka_zaklad = float(castka)
                castka_dph = 0.0
                ucet_dph = None
                smer_dph = None

                # Logika DPH (zkopírována a zjednodušena)
                if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:
                    castka_dph = castka_zaklad * (float(sazba_dph) / 100)
                    sazby = self.get_dph_sazby()
                    info = sazby.get(float(sazba_dph))

                    if smer_dph_popis == 'DPH na VSTUPU (MD)':
                        ucet_dph = info['vstup']
                        smer_dph = 'MD'
                        ucet_protipolozka = ucet_dal
                        smer_protipolozka = 'D'
                    else:
                        ucet_dph = info['vystup']
                        smer_dph = 'D'
                        ucet_protipolozka = ucet_md
                        smer_protipolozka = 'MD'
                else:
                    # Bez DPH
                    if ucet_md.startswith('5') or ucet_md.startswith('0') or ucet_md.startswith('1'):
                        ucet_protipolozka = ucet_dal
                        smer_protipolozka = 'D'
                    else:
                        ucet_protipolozka = ucet_md
                        smer_protipolozka = 'MD'

                castka_celkem = castka_zaklad + castka_dph

                sql_pohyb = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?, ?, ?, ?, ?)"

                # 1. Základ
                ucet_zaklad = ucet_md if smer_protipolozka == 'D' else ucet_dal
                smer_zaklad = 'MD' if smer_protipolozka == 'D' else 'D'
                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_zaklad, smer_zaklad, castka_zaklad))

                # 2. DPH
                if castka_dph > 0 and ucet_dph:
                    cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_dph, smer_dph, castka_dph))

                # 3. Celkem
                cursor.execute(sql_pohyb,
                               (transakce_id, self.klient_id, ucet_protipolozka, smer_protipolozka, castka_celkem))

                conn.commit()
                return True

        except Exception as e:
            print(f"Chyba při editaci: {e}")
            raise e


    def get_ucty_podle_tridy(self, trida_prefix):
        """
        Vrátí seznam účtů, které začínají daným číslem (např. '2' pro třídu 2).
        Vrací list stringů ve formátu: "221 - Běžný bankovní účet".
        """
        # Přidáme % pro SQL LIKE (např. '2%')
        sql = "SELECT ucet, nazev FROM UctovyRozvrh WHERE ucet LIKE ? ORDER BY ucet"
        try:
            results = execute_query(sql, (f"{trida_prefix}%",))
            if not results:
                return []
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání účtů třídy {trida_prefix}: {e}")
            return []
    def get_seznam_uctu(self):
        """Vrátí seznam všech účtů pro výběr ve formuláři (jako list stringů)."""
        sql = "SELECT ucet, nazev FROM UctovyRozvrh ORDER BY ucet"
        try:
            results = execute_query(sql)
            # Vrátí formát: "511 - Opravy a udržování"
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání účtů: {e}")
            return []

    def inicializuj_uctovy_rozvrh(self):
        """
        Naplní tabulku UctovyRozvrh KOMPLETNÍM základním výběrem účtů.
        """
        # Formát: (Účet, Název, Typ: A=Aktiva, P=Pasiva, N=Náklad, V=Výnos)
        kompletni_osnova = [
            # Třída 0 - Dlouhodobý majetek
            ('011', 'Nehmotné výsledky vývoje', 'A'),
            ('012', 'Software', 'A'),
            ('013', 'Ostatní ocenitelná práva', 'A'),
            ('014', 'Goodwill', 'A'),
            ('015', 'Povolenky na emise', 'A'),
            ('016', 'Preferenční limity', 'A'),
            ('019', 'Ostatní dlouhodobý nehmotný majetek', 'A'),
            ('021', 'Stavby', 'A'),
            ('022', 'Hmotné movité věci a jejich soubory', 'A'),
            ('025', 'Pěstitelské celky trvalých porostů', 'A'),
            ('026', 'Dospělá zvířata a jejich skupiny', 'A'),
            ('029', 'Jiný dlouhodobý hmotný majetek', 'A'),
            ('031', 'Pozemky', 'A'),
            ('032', 'Umělecká díla a sbírky', 'A'),
            ('041', 'Nedokončený dlouhodobý nehmotný majetek', 'A'),
            ('042', 'Nedokončený dlouhodobý hmotný majetek', 'A'),
            ('051', 'Poskytnuté zálohy na dlouhodobý nehmotný majetek', 'A'),
            ('052', 'Poskytnuté zálohy na dlouhodobý hmotný majetek', 'A'),
            ('053', 'Poskytnuté zálohy na dlouhodobý finanční majetek', 'A'),
            ('061', 'Podíly – ovládaná nebo ovládající osoba', 'A'),
            ('062', 'Podíly – podstatný vliv', 'A'),
            ('063', 'Ostatní dlouhodobé cenné papíry a podíly', 'A'),
            ('065', 'Dlouhodobé cenné papíry držené do splatnosti', 'A'),
            ('066', 'Zápůjčky a úvěry – ovládaná nebo ovládající osoba', 'A'),
            ('067', 'Ostatní zápůjčky a úvěry', 'A'),
            ('068', 'Zápůjčky a úvěry – podstatný vliv', 'A'),
            ('069', 'Jiný dlouhodobý finanční majetek', 'A'),
            ('072', 'Oprávky k nehmotným výsledkům vývoje', 'A'),
            ('073', 'Oprávky k softwaru', 'A'),
            ('074', 'Oprávky k ostatním ocenitelným právům', 'A'),
            ('075', 'Oprávky ke goodwillu', 'A'),
            ('079', 'Oprávky k ostatnímu dlouhodobému nehmotnému majetku', 'A'),
            ('081', 'Oprávky ke stavbám', 'A'),
            ('082', 'Oprávky k hmotným movitým věcem a jejich souborům', 'A'),
            ('085', 'Oprávky k pěstitelským celkům trvalých porostů', 'A'),
            ('086', 'Oprávky k dospělým zvířatům a jejich skupinám', 'A'),
            ('089', 'Oprávky k jinému dlouhodobému hmotnému majetku', 'A'),
            ('091', 'Opravná položka k dlouhodobému nehmotnému majetku', 'A'),
            ('092', 'Opravná položka k dlouhodobému hmotnému majetku', 'A'),
            ('093', 'Opravná položka k dlouhodobému nedokončenému nehmotnému majetku', 'A'),
            ('094', 'Opravná položka k dlouhodobému nedokončenému hmotnému majetku', 'A'),
            ('095', 'Opravná položka k poskytnutým zálohám na dlouhodobý majetek', 'A'),
            ('096', 'Opravná položka k dlouhodobému finančnímu majetku', 'A'),
            ('097', 'Oceňovací rozdíl k nabytému majetku', 'A'),
            ('098', 'Oprávky k oceňovacímu rozdílu k nabytému majetku', 'A'),
            # Třída 1 - Krátkodobý majetek
            ('111', 'Pořízení materiálu', 'A'),
            ('112', 'Materiál na skladě', 'A'),
            ('119', 'Materiál na cestě', 'A'),
            ('121', 'Nedokončená výroba', 'A'),
            ('122', 'Polotovary vlastní výroby', 'A'),
            ('123', 'Výrobky', 'A'),
            ('124', 'Mladá a ostatní zvířata a jejich skupiny', 'A'),
            ('131', 'Pořízení zboží', 'A'),
            ('132', 'Zboží na skladě a v prodejnách', 'A'),
            ('139', 'Zboží na cestě', 'A'),
            ('151', 'Poskytnuté zálohy na materiál', 'A'),
            ('152', 'Poskytnuté zálohy na mladá zvířata', 'A'),
            ('153', 'Poskytnuté zálohy na zboží', 'A'),
            ('191', 'Opravná položka k materiálu', 'A'),
            ('192', 'Opravná položka k nedokončené výrobě', 'A'),
            ('193', 'Opravná položka k polotovarům vlastní výroby', 'A'),
            ('194', 'Opravná položka k výrobkům', 'A'),
            ('195', 'Opravná položka k mladým zvířatům', 'A'),
            ('196', 'Opravná položka ke zboží', 'A'),
            ('197', 'Opravná položka k zálohám na materiál', 'A'),
            ('198', 'Opravná položka k zálohám na zboží', 'A'),
            ('199', 'Opravná položka k zálohám na mladá zvířata', 'A'),
            # Třída 2 - Finanční účty
            ('211', 'Peněžní prostředky v pokladně', 'A'),
            ('213', 'Ceniny', 'A'),
            ('221', 'Peněžní prostředky na účtech', 'A'),
            ('231', 'Krátkodobé úvěry', 'A'),
            ('232', 'Eskontní úvěry', 'A'),
            ('241', 'Vydané krátkodobé dluhopisy', 'A'),
            ('249', 'Ostatní krátkodobé finanční výpomoci', 'A'),
            ('251', 'Registrované majetkové cenné papíry k obchodování', 'A'),
            ('252', 'Vlastní podíly', 'A'),
            ('253', 'Registrované dluhové cenné papíry k obchodování', 'A'),
            ('254', 'Směnky k inkasu', 'A'),
            ('255', 'Vlastní dluhopisy', 'A'),
            ('256', 'Dluhové cenné papíry se splat. do 1 roku držené do splatnosti', 'A'),
            ('257', 'Ostatní cenné papíry k obchodování', 'A'),
            ('258', 'Podíly – ovládaná nebo ovládající osoba', 'A'),
            ('261', 'Peněžní na cestě', 'A'),
            ('291', 'Opravná položka ke krátkodobému finančnímu majetku', 'A'),
            # Třída 3 - Zúčtovací vztahy
            ('311', 'Odběratelé', 'A'),
            ('312', 'Směnky k inkasu', 'A'),
            ('313', 'Pohledávky za eskontované cenné papíry', 'A'),
            ('314', 'Poskytnuté zálohy – dlouhodobé a krátkodobé', 'A'),
            ('315', 'Ostatní pohledávky', 'A'),
            ('321', 'Závazky z obchodních vztahů', 'P'),
            ('322', 'Směnky k úhradě', 'P'),
            ('324', 'Přijaté zálohy', 'P'),
            ('325', 'Ostatní závazky', 'P'),
            ('331', 'Zaměstnanci', 'P'),
            ('333', 'Ostatní závazky vůči zaměstnancům', 'P'),
            ('335', 'Pohledávky za zaměstnanci', 'A'),
            ('336', 'Zúčtování s institucemi sociál. zabezpečení a zdravot. pojištění', 'P'),
            ('341', 'Daň z příjmů', 'P'),
            ('342', 'Ostatní přímé daně', 'P'),
            ('343', 'Daň z přidané hodnoty', 'P'),
            ('345', 'Ostatní daně a poplatky', 'P'),
            ('346', 'Dotace ze státního rozpočtu', 'P'),
            ('347', 'Ostatní dotace', 'P'),
            ('349', 'Vyrovnávací účet pro DPH', 'A'),
            ('351', 'Pohledávky – ovládaná nebo ovládající osoba', 'A'),
            ('352', 'Pohledávky – podstatný vliv', 'A'),
            ('353', 'Pohledávky za upsaný základní kapitál', 'A'),
            ('354', 'Pohledávky za společníky při úhradě ztráty', 'A'),
            ('355', 'Ostatní pohledávky za společníky obchodní korporace', 'A'),
            ('358', 'Pohledávky za společníky sdruženými ve společnostech', 'A'),
            ('361', 'Závazky – ovládaná nebo ovládající osoba', 'P'),
            ('362', 'Závazky – podstatný vliv', 'P'),
            ('364', 'Závazky ke společníkům při rozdělování zisku', 'P'),
            ('365', 'Ostatní závazky ke společníkům obchodní korporace', 'P'),
            ('366', 'Závazky ke společníkům ze závislé činnosti', 'P'),
            ('367', 'Závazky z upsaných nesplacených cenných papírů a vkladů', 'P'),
            ('368', 'Závazky ke společníkům sdruženým ve společnosti', 'P'),
            ('371', 'Pohledávky z prodeje obchodního závodu', 'A'),
            ('372', 'Závazky z koupě obchodního závodu', 'P'),
            ('373', 'Pohledávky a závazky z pevných termínových operací', 'A'),
            ('374', 'Pohledávky z nájmu a pachtu', 'A'),
            ('375', 'Pohledávky z vydaných dluhopisů', 'A'),
            ('376', 'Nakoupené opce', 'A'),
            ('377', 'Prodané opce', 'P'),
            ('378', 'Jiné pohledávky', 'A'),
            ('379', 'Jiné závazky', 'P'),
            ('381', 'Náklady příštích období', 'A'),
            ('382', 'Komplexní náklady příštích období', 'A'),
            ('383', 'Výdaje příštích období', 'P'),
            ('384', 'Výnosy příštích období', 'P'),
            ('385', 'Příjmy příštích období', 'A'),
            ('388', 'Dohadné účty aktivní', 'A'),
            ('389', 'Dohadné účty pasivní', 'P'),
            ('391', 'Opravná položka k pohledávkám', 'A'),
            ('395', 'Vnitřní zúčtování', 'A'),
            ('398', 'Spojovací účet při společnosti', 'A'),

            #4.Vlastní kapitál adlouhodobé závazky
            ('411', 'Základní kapitál', 'P'),
            ('412', 'Ážio', 'P'),
            ('413', 'Ostatní kapitálové fondy', 'P'),
            ('414', 'Oceňovací rozdíly z přecenění majetku a závazků', 'P'),
            ('416', 'Rozdíly z ocenění při přeměnách obchodních korporací', 'P'),
            ('417', 'Rozdíly z přeměn obchodních korporací', 'P'),
            ('418', 'Oceňovací rozdíly z přecenění při přeměnách obchodních korporací', 'P'),
            ('419', 'Změny základního kapitálu', 'P'),
            ('421', 'Ostatní rezervní fondy', 'P'),
            ('422', 'Nedělitelný fond', 'P'),
            ('423', 'Statutární fond', 'P'),
            ('426', 'Jiný výsledek hospodaření minulých let', 'P'),
            ('427', 'Ostatní fondy', 'P'),
            ('428', 'Nerozdělený zisk minulých let', 'P'),
            ('429', 'Neuhrazená ztráta minulých let', 'P'),
            ('431', 'Výsledek hospodaření ve schvalovacím řízení', 'P'),
            ('432', 'Rozhodnuto o zálohové výplatě podílu na zisku', 'P'),
            ('451', 'Rezervy podle zvláštních právních předpisů', 'P'),
            ('453', 'Rezerva na daň z příjmů', 'P'),
            ('459', 'Ostatní rezervy', 'P'),
            ('461', 'Závazky k úvěrovým institucím', 'P'),
            ('471', 'Dlouhodobé závazky – ovládaná nebo ovládající osoba', 'P'),
            ('472', 'Dlouhodobé závazky – podstatný vliv', 'P'),
            ('473', 'Vydané dluhopisy', 'P'),
            ('474', 'Závazky z nájmu a pachtu', 'P'),
            ('475', 'Dlouhodobě přijaté zálohy', 'P'),
            ('478', 'Dlouhodobé směnky k úhradě', 'P'),
            ('479', 'Jiné dlouhodobé závazky', 'P'),
            ('481', 'Odložený daňový závazek a pohledávka', 'P'),
            ('491', 'Účet individuálního podnikatele', 'P'),
            # Třída 5 - Náklady
            ('501', 'Spotřeba materiálu', 'V'),
            ('502', 'Spotřeba energie', 'V'),
            ('503', 'Spotřeba ostatních neskladovatelných dodávek', 'V'),
            ('504', 'Prodané zboží', 'V'),
            ('511', 'Opravy a udržování', 'V'),
            ('512', 'Cestovné', 'V'),
            ('513', 'Náklady na reprezentaci', 'V'),
            ('518', 'Ostatní služby', 'V'),
            ('521', 'Mzdové náklady', 'V'),
            ('522', 'Příjmy společníků obchodní korporace ze závislé činnosti', 'V'),
            ('523', 'Odměny členům orgánů obchodních korporací', 'V'),
            ('524', 'Zákonné sociální a zdravotní pojištění', 'V'),
            ('525', 'Ostatní sociální a zdravotní pojištění', 'V'),
            ('526', 'Sociální náklady individuálního podnikatele', 'V'),
            ('527', 'Zákonné sociální náklady', 'V'),
            ('528', 'Ostatní sociální náklady', 'V'),
            ('531', 'Daň silniční', 'V'),
            ('532', 'Daň z nemovitých věcí', 'V'),
            ('538', 'Ostatní daně a poplatky', 'V'),
            ('541', 'Zůstatková cena prodaného dlouhodobého nehmotného a hmotného majetku', 'V'),
            ('542', 'Prodaný materiál', 'V'),
            ('543', 'Poskytnuté dary v provozní oblasti', 'V'),
            ('544', 'Smluvní pokuty a úroky z prodlení', 'N'),
            ('545', 'Ostatní pokuty a penále', 'V'),
            ('546', 'Odpis pohledávky', 'V'),
            ('547', 'Mimořádné provozní náklady', 'V'),
            ('548', 'Ostatní provozní náklady', 'V'),
            ('549', 'Manka a škody v provozní oblasti', 'V'),
            ('551', 'Odpisy dlouhodobého nehmotného a hmotného majetku', 'V'),
            ('552', 'Tvorba a zúčtování rezerv podle zvláštních právních předpisů', 'V'),
            ('554', 'Tvorba a zúčtování ostatních rezerv', 'V'),
            ('555', 'Tvorba a zúčtování komplexních nákladů příštích období', 'V'),
            ('557', 'Zúčtování oprávky k oceňovacímu rozdílu k nabytému majetku', 'V'),
            ('558', 'Tvorba a zúčtování zákonných opravných položek', 'V'),
            ('559', 'Tvorba a zúčtování opravných položek', 'V'),
            ('561', 'Prodané cenné papíry a podíly', 'V'),
            ('562', 'Úroky nákladové', 'V'),
            ('563', 'Kurzové ztráty', 'V'),
            ('564', 'Náklady z přecenění majetkových cenných papírů k obchodování', 'V'),
            ('565', 'Poskytnuté dary ve finanční oblasti', 'V'),
            ('566', 'Náklady z finančního majetku', 'V'),
            ('567', 'Náklady z derivátových operací', 'V'),
            ('568', 'Ostatní a mimořádné finanční náklady', 'V'),
            ('569', 'Manka a škody na finančním majetku', 'V'),
            ('574', 'Tvorba a zúčtování finančních rezerv', 'V'),
            ('579', 'Tvorba a zúčtování opravných položek ve finanční činnosti', 'V'),
            ('581', 'Změna stavu nedokončené výroby', 'V'),
            ('582', 'Změna stavu polotovarů', 'V'),
            ('583', 'Změna stavu výrobků', 'V'),
            ('584', 'Změna stavu mladých a ostatních zvířat', 'V'),
            ('585', 'Aktivace materiálu a zboží', 'V'),
            ('586', 'Aktivace vnitropodnikových služeb', 'V'),
            ('587', 'Aktivace dlouhodobého nehmotného majetku', 'V'),
            ('588', 'Aktivace dlouhodobého hmotného majetku', 'V'),
            ('591', 'Daň z příjmů – splatná', 'V'),
            ('592', 'Daň z příjmů – odložená', 'V'),
            ('595', 'Dodatečné odvody daně z příjmů', 'V'),
            ('596', 'Převod podílu na výsledku hospodaření společníkům', 'V'),
            ('597', 'Převod provozních nákladů', 'V'),
            ('598', 'Převod finančních nákladů', 'V'),
            ('599', 'Změna stavu rezervy na daň z příjmů', 'V'),
            # Třída 6 - Výnosy
            ('601', 'Tržby za vlastní výrobky', 'V'),
            ('602', 'Tržby z prodeje služeb', 'V'),
            ('604', 'Tržby za zboží', 'V'),
            ('641', 'Tržby z prodeje dlouhodobého nehmotného a hmotného majetku', 'V'),
            ('642', 'Tržby z prodeje materiálu', 'V'),
            ('644', 'Smluvní pokuty a úroky z prodlení', 'V'),
            ('646', 'Výnosy z odepsaných pohledávek', 'V'),
            ('648', 'Ostatní provozní výnosy', 'V'),
            ('649', 'Mimořádné provozní výnosy', 'V'),
            ('661', 'Tržby z prodeje cenných papírů a podílů', 'V'),
            ('662', 'Úroky výnosové', 'V'),
            ('663', 'Kurzové zisky', 'V'),
            ('664', 'Výnosy z přecenění majetkových cenných papírů k obchodování', 'V'),
            ('665', 'Výnosy z dlouhodobého finančního majetku', 'V'),
            ('666', 'Výnosy z krátkodobého finančního majetku', 'V'),
            ('667', 'Výnosy z derivátových operací', 'V'),
            ('668', 'Ostatní finanční a mimořádné výnosy', 'V'),
            ('669', 'Přijaté dary ve finanční oblasti', 'V'),
            ('697', 'Převod provozních výnosů', 'V'),
            ('698', 'Převod finančních výnosů', 'V'),
            # Ostatní účty
            ('701', 'Počáteční účet rozvažný', 'Z'),
            ('702', 'Konečný účet rozvažný', 'Z'),
            ('710', 'Účet zisků a ztrát', 'Z'),
            ('799', 'Evidenční účet', 'P')
        ]

        inserted_count = 0
        sql = "INSERT INTO UctovyRozvrh (ucet, nazev, typ_uctu) VALUES (?, ?, ?)"

        try:
            with Database() as conn:
                cursor = conn.cursor()
                for ucet, nazev, typ in kompletni_osnova:
                    # Pokusíme se vložit, pokud existuje, přeskočíme (nebo bychom mohli použít MERGE/UPSERT)
                    try:
                        # Rychlá kontrola existence
                        cursor.execute("SELECT 1 FROM UctovyRozvrh WHERE ucet = ?", (ucet,))
                        if not cursor.fetchone():
                            cursor.execute(sql, (ucet, nazev, typ))
                            inserted_count += 1
                    except Exception:
                        pass
                conn.commit()

            return f"Databáze aktualizována. Přidáno {inserted_count} nových účtů."
        except Exception as e:
            return f"Chyba: {e}"

    # --- NOVÁ METODA: ZALOŽENÍ ÚČTU ZA BĚHU (PRO RUČNÍ VSTUP) ---
    def zajisti_existenci_uctu(self, ucet, nazev="Ručně zadaný účet"):
        """
        Pokud účet v databázi neexistuje, vytvoří ho, aby nespadl Foreign Key.
        Odhadne typ účtu podle prvního čísla.
        """
        ucet = ucet.strip()
        sql_check = "SELECT 1 FROM UctovyRozvrh WHERE ucet = ?"

        # Odhad typu podle třídy
        prvni_znak = ucet[0]
        if prvni_znak in ['0', '1', '2']:
            typ = 'A'  # Aktiva
        elif prvni_znak in ['3', '4']:
            typ = 'P'  # Pasiva
        elif prvni_znak == '5':
            typ = 'N'  # Náklady
        elif prvni_znak == '6':
            typ = 'V'  # Výnosy
        elif prvni_znak == '7':
            typ = ['Z', 'P']  # Závěrkové účty
        else:
            typ = 'S'  # Ostatní/System

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_check, (ucet,))
                if not cursor.fetchone():
                    # Účet neexistuje -> Vytvoříme ho
                    sql_insert = "INSERT INTO UctovyRozvrh (ucet, nazev, typ_uctu) VALUES (?, ?, ?)"
                    cursor.execute(sql_insert, (ucet, nazev, typ))
                    conn.commit()
                    return True  # Byl vytvořen
            return False  # Už existoval
        except Exception as e:
            print(f"Chyba při auto-zakládání účtu: {e}")
            return False
    def get_ucet_nazev(self, ucet: str) -> str:
        """Načte název účtu z účtového rozvrhu."""
        sql = "SELECT nazev FROM UctovyRozvrh WHERE ucet = ?"
        result = execute_query(sql, (ucet,))
        return result[0][0] if result else ucet

    def get_zustatek_uctu(self, ucet: str) -> float:
        # Ponecháno, v pořádku
        sql_query = """
        SELECT 
            SUM(CASE WHEN smer = 'MD' THEN castka ELSE 0 END) AS SumaMD,
            SUM(CASE WHEN smer = 'D' THEN castka ELSE 0 END) AS SumaD
        FROM UcetniPohyby
        WHERE klient_id = ? AND ucet = ?
        """
        result = execute_query(sql_query, (self.klient_id, ucet))

        if result and result[0][0] is not None:
            suma_md = result[0][0]
            suma_d = result[0][1]
            # Zůstatek je MD - D
            zustatek = suma_md - suma_d
            return zustatek
        return 0.0

    def get_pohyby_uctu(self, ucet, datum_od=None, datum_do=None):
        """
        Získá detailní pohyby pro konkrétní účet s volitelným časovým filtrem.

        Parametry:
        - ucet (str): Účet (včetně analytiky).
        - datum_od (date/str): Počáteční datum období (včetně).
        - datum_do (date/str): Koncové datum období (včetně).
        """

        # Vybíráme všechny důležité sloupce pro zobrazení v Historii
        sql = """
            SELECT 
                T.datum,
                T.doklad_cislo,
                T.popis AS PopisTransakce,
                P.smer,
                P.castka,
                P.ucet AS ProtipolozkaUcet,
                (SELECT nazev FROM UctovyRozvrh WHERE ucet = P.ucet) AS NazevProtipolozky
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id  
            WHERE T.klient_id = ? 
            AND P.ucet = ? 
            """

        params = [self.klient_id, ucet]

        # --- APLIKACE ČASOVÉHO FILTRU ---
        if datum_od:
            # Převedeme na string, pokud Streamlit vrací date objekt
            datum_od_str = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(datum_od_str)

        if datum_do:
            # Převedeme na string, pokud Streamlit vrací date objekt
            datum_do_str = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(datum_do_str)
        # --- KONEC ČASOVÉHO FILTRU ---

        # Seřadíme podle data pro správné zobrazení historie
        sql += " ORDER BY T.datum, T.id"

        try:
            with Database() as conn:
                df = pd.read_sql_query(sql, conn, params=tuple(params))

            if df.empty:
                return []

            # Přejmenování sloupců pro lepší výstup ve Streamlit (jako to děláte v app.py)
            df.columns = [
                'Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka',
                'Protipolozka Ucet', 'Název Protipoložky'
            ]

            # Ponecháme jen sloupce, které chceme vracet do UI pro finální zobrazení
            df = df[['Datum', 'Doklad Číslo', 'Popis Transakce', 'Směr', 'Částka', 'Název Protipoložky']]

            # Pro zjednodušení kódu v UI/app.py přejmenujeme Název Protipoložky na "Název Účtu"
            # aby to odpovídalo očekávané logice:
            df.rename(columns={'Název Protipoložky': 'Název Účtu'}, inplace=True)

            # Převod na list slovníků pro snadnou práci ve Streamlit
            return df.to_dict('records')

        except Exception as e:
            print(f"Chyba při získávání pohybů pro účet {ucet}: {e}")
            return []

    def spocti_zustatky(self, datum_od=None, datum_do=None):
        """
        Spočítá zůstatky všech účtů.
        Bezpečně ošetřuje None hodnoty z databáze.
        """
        zustatky = defaultdict(float)

        # SQL dotaz
        sql = """
            SELECT 
                P.ucet,
                SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) AS SumaMD,
                SUM(CASE WHEN P.smer = 'D' THEN P.castka ELSE 0 END) AS SumaD
            FROM UcetniPohyby P
            JOIN Transakce T ON T.id = P.transakce_id
            WHERE P.klient_id = ?
            """

        params = [self.klient_id]

        # --- Aplikace filtrů ---
        if datum_od:
            d_od = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(d_od)

        if datum_do:
            d_do = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(d_do)

        sql += " GROUP BY P.ucet"

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                raw_zustatky = cursor.fetchall()

            # Pomocná funkce pro bezpečný převod na číslo
            def safe_float(val):
                if val is None:
                    return 0.0
                try:
                    return float(val)
                except:
                    return 0.0

            for row in raw_zustatky:
                ucet = row[0]
                # Zde byla pravděpodobná chyba - bezpečně načteme čísla
                suma_md = safe_float(row[1])
                suma_d = safe_float(row[2])

                # Zůstatek = MD - D
                zustatky[ucet] = suma_md - suma_d

            return dict(zustatky)

        except Exception as e:
            print(f"CHYBA ve spocti_zustatky: {e}")
            return {}

    # --- NOVÁ METODA PRO DPH ---
    def get_dph_sazby(self) -> dict:
        """Načte sazby DPH z DB a vrátí je jako slovník {procento: {účet_vstup, účet_výstup}}."""
        sql = "SELECT procento, ucet_dph_vstup, ucet_dph_vystup FROM SazbyDPH ORDER BY procento DESC"
        results = execute_query(sql)

        sazby = {}
        for row in results:
            # Ujistěte se, že procento je správně převedeno na float
            procento = float(row[0])
            sazby[procento] = {
                'vstup': row[1],
                'vystup': row[2]
            }
        return sazby

    def spocti_prehled_dph(self, datum_od=None, datum_do=None):
        # --- DEBUG START ---
        print(f"\n=== DEBUG DPH START ===")

        dph_sazby = self.get_dph_sazby()
        prehled = defaultdict(lambda: {'vstup': Decimal('0.0'), 'vystup': Decimal('0.0'), 'rozdil': Decimal('0.0')})
        celkem_rozdil = Decimal('0.0')

        vsechny_dph_ucty = []
        for sazba_dict in dph_sazby.values():
            if sazba_dict['vstup']: vsechny_dph_ucty.append(sazba_dict['vstup'].strip())
            if sazba_dict['vystup']: vsechny_dph_ucty.append(sazba_dict['vystup'].strip())

        vsechny_dph_ucty = list(set(filter(None, vsechny_dph_ucty)))

        if not vsechny_dph_ucty:
            return {'CELKEM': Decimal('0.0')}

        # Přidáme % pro SQL LIKE
        ucet_patterns = [f"{u}%" for u in vsechny_dph_ucty]
        placeholders = " OR ".join(["P.ucet LIKE ?" for _ in ucet_patterns])

        # SQL s JOINem na Transakce kvůli datu
        sql = f"""
            SELECT P.ucet, P.smer, P.castka, T.datum, T.id
            FROM UcetniPohyby P
            JOIN Transakce T ON T.id = P.transakce_id
            WHERE P.klient_id = ? 
            AND ({placeholders})
            """

        params = [self.klient_id] + ucet_patterns

        if datum_od:
            d_od = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(d_od)

        if datum_do:
            d_do = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(d_do)

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                pohyby = cursor.fetchall()

            print(f"DEBUG: Nalezeno {len(pohyby)} relevantních řádků v DB.")

            for row in pohyby:
                # Načtení hodnot z DB a ořezání mezer
                ucet = row[0].strip()
                smer = row[1].strip().upper()  # Převedeme na velká písmena (MD/D)
                raw_castka = row[2] if row[2] is not None else 0.0
                castka_dec = Decimal(str(raw_castka))
                transakce_id = row[4]

                print(f"  -> Řádek ID {transakce_id}: Účet='{ucet}', Směr='{smer}', Částka={castka_dec}")

                matched = False
                for sazba, ucty in dph_sazby.items():
                    # Definice účtů z nastavení (také ořežeme)
                    vstup_cfg = ucty['vstup'].strip() if ucty['vstup'] else None
                    vystup_cfg = ucty['vystup'].strip() if ucty['vystup'] else None

                    # LOGIKA PÁROVÁNÍ
                    # MD = Vstup
                    if vstup_cfg and ucet.startswith(vstup_cfg) and smer == 'MD':
                        prehled[sazba]['vstup'] += castka_dec
                        matched = True
                        break

                    # D = Výstup (Zde je pravděpodobně problém)
                    elif vystup_cfg and ucet.startswith(vystup_cfg) and smer == 'D':
                        prehled[sazba]['vystup'] += castka_dec
                        matched = True
                        break

                if not matched:
                    print(
                        f"     !!! POZOR: Tento řádek nebyl spárován! Zkontrolujte směr '{smer}' vs očekávaný 'D'/'MD'.")

            for sazba, data in prehled.items():
                rozdil = data['vystup'] - data['vstup']
                data['rozdil'] = rozdil
                celkem_rozdil += rozdil

            prehled['CELKEM'] = celkem_rozdil
            print(f"=== DEBUG END. Celkem: {celkem_rozdil} ===")
            return dict(prehled)

        except Exception as e:
            print(f"CHYBA DPH: {e}")
            return {'CELKEM': Decimal('0.0')}


    def get_report_data(self, datum_od=None, datum_do=None):
        """
        Vrátí data pro Rozvahu a Výsledovku na základě skutečného typu účtu v DB (A, P, N, V).
        """
        report = {
            'aktiva': [],
            'pasiva': [],
            'naklady': [],
            'vynosy': [],
            'suma_aktiva': 0.0,
            'suma_pasiva': 0.0,
            'suma_naklady': 0.0,
            'suma_vynosy': 0.0,
            'hospodarsky_vysledek': 0.0
        }

        # SQL: Spojíme Pohyby + Transakce (kvůli datu) + Rozvrh (kvůli typu účtu)
        sql = """
            SELECT 
                P.ucet,
                R.nazev,
                R.typ_uctu,
                SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) as SumaMD,
                SUM(CASE WHEN P.smer = 'D' THEN P.castka ELSE 0 END) as SumaD
            FROM UcetniPohyby P
            JOIN Transakce T ON T.id = P.transakce_id
            JOIN UctovyRozvrh R ON P.ucet = R.ucet
            WHERE P.klient_id = ?
        """

        params = [self.klient_id]

        # Aplikace filtrů
        if datum_od:
            d_od = datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od
            sql += " AND T.datum >= ?"
            params.append(d_od)

        if datum_do:
            d_do = datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do
            sql += " AND T.datum <= ?"
            params.append(d_do)

        sql += " GROUP BY P.ucet, R.nazev, R.typ_uctu ORDER BY P.ucet"

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()

            for row in rows:
                ucet = row[0]
                nazev = row[1]
                typ = row[2]  # Tady máme 'A', 'P', 'N', 'V' přímo z DB
                suma_md = float(row[3]) if row[3] else 0.0
                suma_d = float(row[4]) if row[4] else 0.0

                # Výpočet zůstatku (MD - D)
                # Kladné číslo = převaha MD, Záporné číslo = převaha D
                zustatek_raw = suma_md - suma_d

                # Ignorujeme nulové zůstatky
                if abs(zustatek_raw) < 0.01:
                    continue

                polozka = {'ucet': ucet, 'nazev': nazev}

                # --- LOGIKA ROZDĚLENÍ PODLE TYPU Z DB ---

                if typ == 'A':  # AKTIVA
                    # Aktiva mají mít zůstatek na MD (kladný).
                    polozka['castka'] = zustatek_raw
                    report['aktiva'].append(polozka)
                    report['suma_aktiva'] += zustatek_raw

                elif typ == 'P':  # PASIVA
                    # Pasiva mají mít zůstatek na D (záporný v naší logice MD-D).
                    # Pro report je převedeme na kladné číslo pomocí abs().
                    polozka['castka'] = abs(zustatek_raw)
                    report['pasiva'].append(polozka)
                    report['suma_pasiva'] += abs(zustatek_raw)

                elif typ == 'N':  # NÁKLADY
                    # Náklady jsou na MD (kladné)
                    polozka['castka'] = zustatek_raw
                    report['naklady'].append(polozka)
                    report['suma_naklady'] += zustatek_raw

                elif typ == 'V':  # VÝNOSY
                    # Výnosy jsou na D (záporné v logice MD-D).
                    # Převedeme na kladné pro zobrazení.
                    polozka['castka'] = abs(zustatek_raw)
                    report['vynosy'].append(polozka)
                    report['suma_vynosy'] += abs(zustatek_raw)

                # (Typy Z, S atd. zatím ignorujeme, pokud nejsou součástí výkazů)

            # --- VÝPOČET ZISKU (HV) ---
            # Zisk = Výnosy - Náklady
            hv = report['suma_vynosy'] - report['suma_naklady']
            report['hospodarsky_vysledek'] = hv

            # --- ZAROVNÁNÍ BILANCE ---
            # Zisk je zdrojem krytí majetku -> patří do PASIV
            # Ztráta snižuje vlastní kapitál -> snižuje PASIVA (je tam jako záporná položka nebo minus v pasivech)
            if abs(hv) > 0.005:
                report['pasiva'].append({
                    'ucet': 'HV',
                    'nazev': 'Výsledek hospodaření (Zisk/Ztráta)',
                    'castka': hv  # Pokud je zisk, přičte se k pasivům. Pokud ztráta, odečte se.
                })
                report['suma_pasiva'] += hv

            return report

        except Exception as e:
            print(f"Chyba při generování reportu: {e}")
            return report


    # --- PŘEPRACOVANÁ METODA PRO UKLÁDÁNÍ TRANSAKCE (Nyní s DPH) ---
    def save_transakce(self, datum, popis, doklad_cislo, ucet_md_zaklad, ucet_dal_zaklad, castka_bez_dph, sazba_dph,
                       smer_dph_popis):

        self.zkontroluj_zda_je_otevreno(datum)
        # 0. PŘÍPRAVA DAT DPH
        castka_zaklad = float(castka_bez_dph)
        castka_dph = 0.0

        if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:

            castka_dph = castka_zaklad * (float(sazba_dph) / 100)
            sazby_info = self.get_dph_sazby()
            info = sazby_info.get(float(sazba_dph))

            if not info:
                raise ValueError(f"Nenalezeny účty pro sazbu DPH: {sazba_dph}")

            # Určení účtu a směru DPH
            if smer_dph_popis == 'DPH na VSTUPU (MD)':
                ucet_dph = info['vstup']
                smer_dph = 'MD'
                # Protipoložka, která nese celkem (např. 321) je na DAL
                ucet_protipolozka = ucet_dal_zaklad
                smer_protipolozka = 'D'
            else:  # DPH na VÝSTUPU (D)
                ucet_dph = info['vystup']
                smer_dph = 'D'
                # Protipoložka, která nese celkem (např. 221) je na MD
                ucet_protipolozka = ucet_md_zaklad
                smer_protipolozka = 'MD' # <--- ZAJIŠTĚNO, ŽE JE DEFINOVÁNO VŽDY

        else:
            # Neúčtuje se DPH, transakce je jen na základní částku
            castka_dph = 0.0
            ucet_dph = None

            # Nastavíme základní směr účtování (musí se vybrat jeden z MD/DAL)
            # Předpoklad: Při nákupu je protipoložka D (závazek), při prodeji MD (banka/pohledávka)
            if ucet_md_zaklad in ['511', '501']:  # Typický MD náklad
                ucet_protipolozka = ucet_dal_zaklad  # 321, 221
                smer_protipolozka = 'D' # <--- ZDE BYLO DEFINOVÁNO
            else:  # Typický D výnos (602)
                ucet_protipolozka = ucet_md_zaklad  # 221, 311
                smer_protipolozka = 'MD' # <--- TOTO BYLO PŘIDÁNO!


        castka_celkem = castka_zaklad + castka_dph

        sql_transakce = """
        INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo)
        VALUES (?, ?, ?, ?);
        """
        sql_pohyb = """
        INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka)
        VALUES (?, ?, ?, ?, ?);
        """

        try:
            with Database() as conn:
                cursor = conn.cursor()

                # --- 1. VLOŽENÍ HLAVIČKY TRANSAKCE + ZÍSKÁNÍ ID ---
                sql_insert_and_get_id = sql_transakce + "SELECT SCOPE_IDENTITY();"
                cursor.execute(sql_insert_and_get_id, (self.klient_id, datum, popis, doklad_cislo))

                # Získání ID
                cursor.nextset()
                transakce_id = cursor.fetchone()[0]

                # --- POHYBY ---

                # 1. POHYB ZÁKLADU
                # Určíme účet základu (ten, který NENÍ protipoložkou) a jeho směr (opak protipoložky)
                ucet_zaklad = ucet_md_zaklad if smer_protipolozka == 'D' else ucet_dal_zaklad
                smer_zaklad = 'MD' if smer_protipolozka == 'D' else 'D'

                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_zaklad, smer_zaklad, castka_zaklad))

                # 2. POHYB DPH (Pokud se účtuje)
                if castka_dph > 0 and ucet_dph:
                    cursor.execute(sql_pohyb, (transakce_id, self.klient_id, ucet_dph, smer_dph, castka_dph))

                # 3. PROTIPOLOŽKA (Celková částka nebo Základ)
                # Použijeme castka_celkem, i když DPH=0, protože castka_celkem = castka_zaklad + 0
                cursor.execute(sql_pohyb,
                               (transakce_id, self.klient_id, ucet_protipolozka, smer_protipolozka, castka_celkem))

                conn.commit()
                return int(transakce_id)

        except Exception as e:
            if '_conn' in locals() and conn._conn:
                conn._conn.rollback()
            print(f"Chyba při ukládání transakce do DB: {e}")
            return None

    # ==========================================
    # NOVÉ METODY PRO UZÁVĚRKU (VLOŽIT DO TŘÍDY)
    # ==========================================

    def get_datum_uzaverky(self):
        """Vrátí datum poslední uzávěrky (nebo None)."""
        # POZOR: Ujistěte se, že máte v DB sloupec datum_uzaverky (viz Krok 2 níže)
        sql = "SELECT datum_uzaverky FROM Klienti WHERE id = ?"
        try:
            res = execute_query(sql, (self.klient_id,))
            if res and res[0][0]:
                return res[0][0]  # Vrací date objekt nebo string
            return None
        except Exception:
            # Pokud sloupec neexistuje, vrátíme None (aby aplikace nespadla, dokud neupravíte DB)
            return None

    def set_datum_uzaverky(self, nove_datum):
        """Nastaví datum, do kterého je účetnictví uzamčeno."""
        sql = "UPDATE Klienti SET datum_uzaverky = ? WHERE id = ?"
        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (nove_datum, self.klient_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"Chyba při uzávěrce: {e}")
            return False

    def zkontroluj_zda_je_otevreno(self, datum_transakce):
        """
        Vyhodí chybu, pokud je datum_transakce v uzavřeném období.
        """
        uzavreno_do = self.get_datum_uzaverky()

        if not uzavreno_do:
            return  # Žádná uzávěrka = vše povoleno

        # Pokud je datum_transakce string, převedeme na date objekt
        if isinstance(datum_transakce, str):
            from datetime import datetime
            try:
                datum_transakce = datetime.strptime(datum_transakce, '%Y-%m-%d').date()
            except:
                pass  # Pokud konverze selže, necháme to být (pravděpodobně je to už date)

        # Porovnání
        if datum_transakce <= uzavreno_do:
            datum_str = datum_transakce.strftime('%d.%m.%Y') if hasattr(datum_transakce, 'strftime') else str(
                datum_transakce)
            uzaverka_str = uzavreno_do.strftime('%d.%m.%Y')
            raise ValueError(f"⛔ Období je uzamčeno! (Uzávěrka do {uzaverka_str}). Nelze účtovat k {datum_str}.")

    # ==========================================
    # METODA PRO ROČNÍ UZÁVĚRKU (710)
    # ==========================================
    def provest_uctovani_uzaverky_710(self, datum_uzaverky):
        """
        Spočítá zůstatky všech účtů 5xx a 6xx od začátku roku do datum_uzaverky.
        Vytvoří hromadný doklad, který je vynuluje proti účtu 710.
        """
        rok = datum_uzaverky.year
        datum_od = date(rok, 1, 1)

        # 1. Získání zůstatků (agregace po účtech)
        sql_balance = """
            SELECT P.ucet, SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END) as bilance
            FROM UcetniPohyby P
            JOIN Transakce T ON P.transakce_id = T.id
            WHERE T.klient_id = ? 
              AND T.datum >= ? AND T.datum <= ?
              AND (P.ucet LIKE '5%' OR P.ucet LIKE '6%')
            GROUP BY P.ucet
            HAVING SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END) <> 0
        """

        try:
            # Zajistíme existenci účtu 710
            self.zajisti_existenci_uctu("710", "Účet zisků a ztrát")

            pohyby_k_uctovani = execute_query(sql_balance, (self.klient_id, datum_od, datum_uzaverky))

            if not pohyby_k_uctovani:
                return "Žádné zůstatky k uzavření (náklady a výnosy jsou 0)."

            with Database() as conn:
                cursor = conn.cursor()

                # A) Vytvoření hlavičky transakce
                doklad_cislo = f"UZAV-{rok}"
                popis = f"Uzávěrka nákladů a výnosů k {rok}"

                # Pozor: Pokud je období uzamčeno, musíme to obejít nebo zkontrolovat.
                # Předpokládáme, že uživatel to dělá PŘED zamčením nebo to systém při této speciální akci dovolí.
                # self.zkontroluj_zda_je_otevreno(datum_uzaverky) # Odkomentujte, pokud chcete striktní kontrolu

                cursor.execute("""
                    INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo, created_at)
                    VALUES (?, ?, ?, ?, GETDATE());
                    SELECT SCOPE_IDENTITY();
                """, (self.klient_id, datum_uzaverky, popis, doklad_cislo))

                transakce_id = cursor.fetchone()[0]

                # B) Generování pohybů
                sql_insert = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?, ?, ?, ?, ?)"

                celkem_md_710 = 0.0
                celkem_d_710 = 0.0

                for row in pohyby_k_uctovani:
                    ucet = row[0]
                    bilance = float(row[1])  # Kladná = převažuje MD (Náklad), Záporná = převažuje D (Výnos)

                    if bilance > 0:
                        # Je to NÁKLAD (má zůstatek na MD). Abychom ho vynulovali, musíme účtovat na D.
                        # Protiúčet 710 bude na MD.
                        castka = abs(bilance)
                        # 1. Vynulování pětky (Dal)
                        cursor.execute(sql_insert, (transakce_id, self.klient_id, ucet, 'D', castka))
                        # 2. Načtení na 710 (MD) - ale 710 sečteme a zapíšeme až na konci, nebo po řádcích?
                        # Zapisujme po řádcích, je to přehlednější v deníku (vidíme z jakého účtu to přišlo).
                        cursor.execute(sql_insert, (transakce_id, self.klient_id, '710', 'MD', castka))

                    elif bilance < 0:
                        # Je to VÝNOS (má zůstatek na D). Abychom ho vynulovali, musíme účtovat na MD.
                        # Protiúčet 710 bude na D.
                        castka = abs(bilance)
                        # 1. Vynulování šestky (Má Dáti)
                        cursor.execute(sql_insert, (transakce_id, self.klient_id, ucet, 'MD', castka))
                        # 2. Načtení na 710 (Dal)
                        cursor.execute(sql_insert, (transakce_id, self.klient_id, '710', 'D', castka))

                conn.commit()
                return f"✅ Uzávěrka úspěšná! Vytvořen doklad {doklad_cislo} (ID {transakce_id})."

        except Exception as e:
            return f"❌ Chyba při uzávěrce: {e}"
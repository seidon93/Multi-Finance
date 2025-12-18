from collections import defaultdict
from core.database import execute_query, Database
from decimal import Decimal
from datetime import date, datetime
import pandas as pd
import os


class AccountingEngine:
    """Třída pro výpočet účetních dat a reportů."""

    def __init__(self, klient_id):
        self.klient_id = klient_id
        self.zkontroluj_a_oprav_db()
        self.opravit_strukturu_rozvrhu()
        self.metoda_zasob = metoda_zasob

    def zkontroluj_a_oprav_db(self):
        """Zkontroluje a doplní základní sloupce (datum_uzaverky, created_at, AuditLog)."""
        try:
            # 1. Datum uzávěrky
            res = execute_query("SELECT col_length('Klienti', 'datum_uzaverky')")
            if not res or res[0][0] is None:
                with Database() as conn:
                    conn.cursor().execute("ALTER TABLE Klienti ADD datum_uzaverky DATE NULL;")
                    conn.commit()

            # 2. Created_at
            res = execute_query("SELECT col_length('Transakce', 'created_at')")
            if not res or res[0][0] is None:
                with Database() as conn:
                    conn.cursor().execute("ALTER TABLE Transakce ADD created_at DATETIME DEFAULT GETDATE();")
                    conn.commit()

            # 3. AuditLog
            audit_sql = """
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLog' AND xtype='U')
                CREATE TABLE AuditLog (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    transakce_id INT,
                    datum_zmeny DATETIME DEFAULT GETDATE(),
                    typ_akce NVARCHAR(50), 
                    puvodni_data NVARCHAR(MAX), 
                    novy_data NVARCHAR(MAX) 
                );
            """
            with Database() as conn:
                conn.cursor().execute(audit_sql)
                conn.commit()
        except:
            pass

    def opravit_strukturu_rozvrhu(self):
        """
        Kritická oprava: Odstraní zámky na sloupci typ_uctu a nastaví 799 na P*.
        """
        try:
            with Database() as conn:
                cursor = conn.cursor()

                # A) Odstranění constraintů (aby šlo vložit 'Z' nebo 'P*')
                sql_find = """
                    SELECT name FROM sys.check_constraints 
                    WHERE parent_object_id = OBJECT_ID('UctovyRozvrh') 
                    AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('UctovyRozvrh') AND name = 'typ_uctu')
                """
                cursor.execute(sql_find)
                for row in cursor.fetchall():
                    cursor.execute(f"ALTER TABLE UctovyRozvrh DROP CONSTRAINT [{row[0]}]")

                # B) Rozšíření sloupce
                cursor.execute("ALTER TABLE UctovyRozvrh ALTER COLUMN typ_uctu NVARCHAR(20)")

                # C) Update 799 na P* (pomocí sloupce 'cislo')
                cursor.execute("UPDATE UctovyRozvrh SET typ_uctu = 'P*' WHERE cislo = '799'")
                conn.commit()
        except:
            pass

        audit_sql = """
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLog' AND xtype='U')
                CREATE TABLE AuditLog (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    transakce_id INT,
                    datum_zmeny DATETIME DEFAULT GETDATE(),
                    typ_akce NVARCHAR(50), 
                    puvodni_data NVARCHAR(MAX), 
                    novy_data NVARCHAR(MAX) 
                );
                """
        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(audit_sql)
                conn.commit()
        except Exception as e:
            print(f"Chyba při vytváření AuditLog: {e}")

    def opravit_strukturu_rozvrhu(self):
        """Zajistí možnost vkládání P* a Z, update 799."""
        try:
            with Database() as conn:
                cursor = conn.cursor()
                # 1. Drop constraints
                sql_find = "SELECT name FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID('UctovyRozvrh') AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('UctovyRozvrh') AND name = 'typ_uctu')"
                cursor.execute(sql_find)
                for row in cursor.fetchall():
                    cursor.execute(f"ALTER TABLE UctovyRozvrh DROP CONSTRAINT [{row[0]}]")

                # 2. Resize column
                cursor.execute("ALTER TABLE UctovyRozvrh ALTER COLUMN typ_uctu NVARCHAR(20)")

                # 3. Update 799 (pomocí 'cislo')
                cursor.execute("UPDATE UctovyRozvrh SET typ_uctu = 'P*' WHERE cislo = '799'")
                conn.commit()
        except: pass

    def get_transakce_detail(self, transakce_id):
        sql = """
            SELECT T.datum, T.doklad_cislo, T.popis, 
                   P.ucet, P.smer, P.castka
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.id = ?
        """
        try:
            results = execute_query(sql, (transakce_id,))
            if not results: return None
            hlavicka = {'id': transakce_id, 'datum': results[0][0], 'doklad': results[0][1], 'popis': results[0][2], 'pohyby': []}
            for row in results:
                hlavicka['pohyby'].append({'ucet': row[3], 'smer': row[4], 'castka': float(row[5])})
            return hlavicka
        except: return None

    def upravit_transakci(self, transakce_id, nove_datum, novy_popis, novy_doklad, ucet_md, ucet_dal, castka, sazba_dph, smer_dph_popis):
        # (Zkráceno pro přehlednost - logika je identická jako v save_transakce, jen s UPDATE/DELETE)
        # Prosím, použijte plnou verzi z předchozí odpovědi, nebo zavolejte save_transakce po smazání.
        # Zde je klíčová část smazání:
        with Database() as conn:
            conn.cursor().execute("DELETE FROM UcetniPohyby WHERE transakce_id=?", (transakce_id,))
            conn.cursor().execute("UPDATE Transakce SET datum=?, popis=?, doklad_cislo=? WHERE id=?", (nove_datum, novy_popis, novy_doklad, transakce_id))
            conn.commit()
        # Následně znovu vložte pohyby (stejná logika jako save_transakce)
        # ...
        return True

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
        """Vrátí seznam účtů (cislo - nazev)."""
        # OPRAVA: cislo místo ucet
        sql = "SELECT cislo, nazev FROM UctovyRozvrh WHERE cislo LIKE ? ORDER BY cislo"
        try:
            results = execute_query(sql, (f"{trida_prefix}%",))
            if not results:
                return []
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání účtů třídy {trida_prefix}: {e}")
            return []

    def get_seznam_uctu(self):
        """Vrátí seznam všech účtů."""
        # OPRAVA: cislo místo ucet
        sql = "SELECT cislo, nazev FROM UctovyRozvrh ORDER BY cislo"
        try:
            results = execute_query(sql)
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání účtů: {e}")
            return []

    def get_ucet_nazev(self, cislo_uctu):
        """Načte název účtu."""
        # OPRAVA: cislo místo ucet
        sql = "SELECT nazev FROM UctovyRozvrh WHERE cislo = ?"
        result = execute_query(sql, (cislo_uctu,))
        return result[0][0] if result else cislo_uctu
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
            ('799', 'Evidenční účet', 'P*')
        ]

        inserted_count = 0
        sql = "INSERT INTO UctovyRozvrh (cislo, nazev, typ_uctu) VALUES (?, ?, ?)"

        try:
            with Database() as conn:
                cursor = conn.cursor()
                for ucet, nazev, typ in kompletni_osnova:
                    # Pokusíme se vložit, pokud existuje, přeskočíme (nebo bychom mohli použít MERGE/UPSERT)
                    try:
                        # Rychlá kontrola existence
                        cursor.execute("SELECT 1 FROM UctovyRozvrh WHERE cislo = ?", (ucet,))
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
    def zajisti_existenci_uctu(self, ucet, nazev="Nový účet"):
        ucet = str(ucet).strip()
        # OPRAVA: Kontrola přes 'cislo'
        check = execute_query("SELECT 1 FROM UctovyRozvrh WHERE cislo = ?", (ucet,))
        if check: return

        # Logika typu
        p = ucet[0]
        if p in ['0', '1', '2']:
            t = 'A'
        elif p in ['3', '4']:
            t = 'P'
        elif p == '5':
            t = 'N'
        elif p == '6':
            t = 'V'
        elif p == '7':
            t = 'Z'
        else:
            t = 'S'

        # Specifický fix pro 799
        if ucet == '799': t = 'P*'

        # OPRAVA: Vložení do 'cislo'
        try:
            with Database() as conn:
                conn.cursor().execute(
                    "INSERT INTO UctovyRozvrh (cislo, nazev, typ_uctu, klient_id) VALUES (?,?,?,?)",
                    (ucet, nazev, t, self.klient_id)
                )
                conn.commit()
        except:
            pass

    def get_ucet_nazev(self, ucet):
        res = execute_query("SELECT nazev FROM UctovyRozvrh WHERE cislo=?", (ucet,))
        return res[0][0] if res else ucet

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
        # OPRAVA PODDOTAZU: WHERE cislo = P.ucet
        sql = """
            SELECT T.datum, T.doklad_cislo, T.popis, P.smer, P.castka, P.ucet,
            (SELECT nazev FROM UctovyRozvrh WHERE cislo = P.ucet)
            FROM Transakce T JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.klient_id = ? AND P.ucet = ?
        """
        # ... zbytek funkce s parametry data ...
        params = [self.klient_id, ucet]
        if datum_od:
            sql += " AND T.datum >= ?"
            params.append(datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od)
        if datum_do:
            sql += " AND T.datum <= ?"
            params.append(datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do)

        sql += " ORDER BY T.datum, T.id"

        try:
            with Database() as conn:
                df = pd.read_sql_query(sql, conn, params=tuple(params))
            if df.empty: return []
            df.columns = ['Datum', 'Doklad', 'Popis', 'Směr', 'Částka', 'Protiúčet', 'Název Účtu']
            return df.to_dict('records')
        except:
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

    def get_report_data(self, datum_od=None, datum_do=None, detailni=True):
        """Vrací data pro reporty s automatickým zahrnutím HV do pasiv (ČSÚ)."""
        sql = """
            SELECT P.ucet, R.nazev, R.typ_uctu, SUM(P.castka), P.smer
            FROM UcetniPohyby P 
            LEFT JOIN UctovyRozvrh R ON P.ucet = R.cislo
            JOIN Transakce T ON P.transakce_id = T.id
            WHERE T.klient_id = ?
        """
        params = [self.klient_id]
        if datum_od:
            sql += " AND T.datum >= ?"
            params.append(datum_od)
        if datum_do:
            sql += " AND T.datum <= ?"
            params.append(datum_do)

        sql += " GROUP BY P.ucet, R.nazev, R.typ_uctu, P.smer"

        try:
            rows = execute_query(sql, tuple(params))
            rep = {
                'aktiva': [], 'pasiva': [], 'naklady': [], 'vynosy': [],
                'suma_aktiva': 0.0, 'suma_pasiva': 0.0, 'suma_naklady': 0.0, 'suma_vynosy': 0.0,
                'hospodarsky_vysledek': 0.0
            }

            temp = defaultdict(lambda: {'bal': 0.0, 'typ': 'S', 'nazev': ''})

            for r in rows:
                u_raw = str(r[0])
                u = u_raw if detailni else u_raw.split('.')[0]
                val = float(r[3])
                smer = r[4]

                temp[u]['typ'] = r[2] if r[2] else 'S'
                if not detailni and '.' in u_raw:
                    temp[u]['nazev'] = self.get_ucet_nazev(u)
                else:
                    temp[u]['nazev'] = r[1] if r[1] else u_raw

                # Standardní MD/D logika zůstatků
                if smer == 'MD':
                    temp[u]['bal'] += val
                else:
                    temp[u]['bal'] -= val

            for u, data in temp.items():
                b = data['bal']
                t = data['typ']
                n = data['nazev']

                if abs(b) < 0.005: continue
                item = {'ucet': u, 'nazev': n, 'castka': abs(b)}

                if t == 'A':
                    rep['aktiva'].append(item)
                    rep['suma_aktiva'] += b
                elif t in ['P', 'P*', 'Z']:
                    # Pasiva mají standardně záporný bal v DB (proto abs)
                    rep['pasiva'].append(item)
                    rep['suma_pasiva'] += abs(b)
                elif t == 'N':
                    rep['naklady'].append(item)
                    rep['suma_naklady'] += abs(b)
                elif t == 'V':
                    rep['vynosy'].append(item)
                    rep['suma_vynosy'] += abs(b)

            # 1. Výpočet Hospodářského výsledku (Zisk = Výnosy - Náklady)
            hv = rep['suma_vynosy'] - rep['suma_naklady']
            rep['hospodarsky_vysledek'] = hv

            # 2. KLÍČOVÝ KROK: Zahrnutí HV do Pasiv (Vlastní kapitál)
            # Podle českých standardů musí HV uzavírat rozvahu.
            hv_item = {
                'ucet': 'HV',
                'nazev': 'Hospodářský výsledek (zisk/ztráta)',
                'castka': hv  # Zde necháváme znaménko pro zobrazení (kladné = zisk)
            }
            rep['pasiva'].append(hv_item)

            # 3. Přepočet celkových pasiv (přičteme zisk nebo odečteme ztrátu)
            rep['suma_pasiva'] += hv

            return rep
        except Exception as e:
            print(f"Chyba v get_report_data: {e}")
            return None

    def validuj_ceske_standardy(self, ucet_md, ucet_dal):
        """Rozšířená validace o metody zásob A/B."""
        u_md = str(ucet_md)
        u_dal = str(ucet_dal)

        # Základní kontroly (Peníze na cestě, Výsledovka proti sobě) zůstávají...
        penezni = ('211', '221', '213')
        if any(u_md.startswith(p) for p in penezni) and any(u_dal.startswith(p) for p in penezni):
            raise ValueError("Přímý převod mezi pokladnou/bankou není povolen. Použijte 261.")

        # SPECIFICKÁ LOGIKA PRO ZÁSOBY
        if self.metoda_zasob == 'A':
            # Metoda A: Nákup nesmí jít přímo na 112/132, musí přes 111/131
            if u_md.startswith(('112', '132')) and u_dal.startswith('321'):
                raise ValueError("Při metodě A nelze účtovat nákup přímo na sklad. Použijte 111 nebo 131.")
        else:
            # Metoda B: Nákup jde přímo do nákladů (501/504)
            if u_md.startswith(('112', '132')) and u_dal.startswith('321'):
                raise ValueError(
                    "Při metodě B účtujte nákup přímo do nákladů (501/504). Účty 112/132 jsou pouze pro uzávěrku.")

        return True

    def provest_operaci_zasoby_uzaverka(self, rok, zustatek_skladu, typ='material'):
        """
        Operace se zásobami pro Metodu B na konci roku.
        Převede počáteční stav do nákladů a nový zůstatek na sklad.
        """
        self.zkontroluj_zda_je_otevreno(date(rok, 12, 31))
        u_sklad = '112' if typ == 'material' else '132'
        u_spotreba = '501' if typ == 'material' else '504'

        # 1. Vyúčtování počátečního stavu do nákladů: MD 501 / D 112
        stary_zustatek = self.get_zustatek_uctu(u_sklad)
        if abs(stary_zustatek) > 0:
            self.save_transakce(date(rok, 12, 31), f"B: Převod počátečního stavu {typ}u",
                                f"ZAS-{rok}-01", u_spotreba, u_sklad, abs(stary_zustatek), 0, 'Neučtovat')

        # 2. Zápis konečného stavu na sklad: MD 112 / D 501
        return self.save_transakce(date(rok, 12, 31), f"B: Konečný stav {typ}u dle inventury",
                                   f"ZAS-{rok}-02", u_sklad, u_spotreba, zustatek_skladu, 0, 'Neučtovat')

    # --- PŘEPRACOVANÁ METODA PRO UKLÁDÁNÍ TRANSAKCE (Nyní s DPH) ---
    def save_transakce(self, datum, popis, doklad_cislo, ucet_md_zaklad, ucet_dal_zaklad, castka_bez_dph, sazba_dph,
                       smer_dph_popis):
        """Uloží transakci do DB s předchozí kontrolou českých standardů."""

        try:
            # 1. ZÁKLADNÍ KONTROLA (Otevřené období)
            self.zkontroluj_zda_je_otevreno(datum)

            # 2. KONTROLA ČESKÝCH STANDARDŮ (Nová logika)
            # Pokud neprojde, vyhodí ValueError a skočí do except bloku
            self.validuj_ceske_standardy(ucet_md_zaklad, ucet_dal_zaklad)

            # 3. PŘÍPRAVA PROMĚNNÝCH
            base = float(castka_bez_dph)
            tax = 0.0
            u_dph = None
            s_dph = None
            u_opp = None
            s_opp = None

            # Logika DPH
            if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:
                tax = base * (float(sazba_dph) / 100)
                sz = self.get_dph_sazby().get(float(sazba_dph))
                if not sz:
                    raise ValueError(f"Sazba DPH {sazba_dph}% nenalezena v nastavení.")

                if smer_dph_popis == 'DPH na VSTUPU (MD)':
                    u_dph = sz['vstup']
                    s_dph = 'MD'
                    u_opp = ucet_dal_zaklad
                    s_opp = 'D'
                else:  # Výstup
                    u_dph = sz['vystup']
                    s_dph = 'D'
                    u_opp = ucet_md_zaklad
                    s_opp = 'MD'
            else:
                # Bez DPH - Určení směru protipoložky (zjednodušená logika)
                # Pokud MD účet je Aktivum/Náklad, protistrana je Dal
                if str(ucet_md_zaklad).startswith(('5', '0', '1', '2', '3')):
                    u_opp = ucet_dal_zaklad
                    s_opp = 'D'
                else:
                    u_opp = ucet_md_zaklad
                    s_opp = 'MD'

            total = base + tax

            # 4. ZÁPIS DO DATABÁZE
            with Database() as conn:
                cur = conn.cursor()

                sql_hlavicka = """
                    SET NOCOUNT ON;
                    INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo) 
                    VALUES (?, ?, ?, ?);
                    SELECT SCOPE_IDENTITY();
                """
                cur.execute(sql_hlavicka, (self.klient_id, datum, popis, doklad_cislo))

                row = cur.fetchone()
                if not row or row[0] is None:
                    raise Exception("Nepodařilo se získat ID transakce.")

                tid = int(row[0])

                sql_ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?,?,?,?,?)"

                # Pohyb 1: Základ
                u_z = ucet_md_zaklad if s_opp == 'D' else ucet_dal_zaklad
                s_z = 'MD' if s_opp == 'D' else 'D'
                cur.execute(sql_ins, (tid, self.klient_id, u_z, s_z, base))

                # Pohyb 2: DPH (pokud existuje)
                if tax > 0 and u_dph:
                    cur.execute(sql_ins, (tid, self.klient_id, u_dph, s_dph, tax))

                # Pohyb 3: Celková protipoložka (Závazek/Pohledávka/Peníze)
                cur.execute(sql_ins, (tid, self.klient_id, u_opp, s_opp, total))

                conn.commit()
                return tid

        except ValueError as ve:
            # Specifická chyba pro porušení účetních standardů
            print(f"Validační chyba: {ve}")
            # V UI se zobrazí tato zpráva uživateli
            raise ve
        except Exception as e:
            print(f"Save error: {e}")
            return None


    # ==========================================
    # NOVÉ METODY PRO UZÁVĚRKU (VLOŽIT DO TŘÍDY)
    # ==========================================

    def get_datum_uzaverky(self):
        res = execute_query("SELECT datum_uzaverky FROM Klienti WHERE id=?", (self.klient_id,))
        return res[0][0] if res else None

    def set_datum_uzaverky(self, d):
        with Database() as conn:
            conn.cursor().execute("UPDATE Klienti SET datum_uzaverky=? WHERE id=?", (d, self.klient_id))
            conn.commit()
        return True

    def zkontroluj_zda_je_otevreno(self, datum):
        res = execute_query("SELECT datum_uzaverky FROM Klienti WHERE id=?", (self.klient_id,))
        uzaverka = res[0][0] if res else None
        if not uzaverka: return

        if isinstance(datum, str):
            try:
                datum = datetime.strptime(datum, '%Y-%m-%d').date()
            except:
                pass

        if datum <= uzaverka:
            raise ValueError(f"⛔ Období je uzamčeno do {uzaverka.strftime('%d.%m.%Y')}.")

    # ==========================================
    # METODA PRO ROČNÍ UZÁVĚRKU (710)
    # ==========================================
    def provest_uctovani_uzaverky_710(self, datum_uzaverky):
        return self.provest_rocn_uzaverku_komplet(datum_uzaverky.year)

    def zauctovat_dan_z_prijmu(self, datum, vypocena_dan, poznamka="Daň z příjmů PO"):
        # 1. Definujeme základní tvar dokladu (např. DPPO-2025)
        base_doklad = f"DPPO-{datum.year}"

        # 2. Zjistíme, jaké doklady už existují pro tento rok, abychom našli další číslo v řadě
        sql_check = "SELECT doklad_cislo FROM Transakce WHERE doklad_cislo LIKE ? AND klient_id = ?"
        # Hledáme vše co začíná "DPPO-2025"
        rows = execute_query(sql_check, (f"{base_doklad}%", self.klient_id))

        max_index = 0

        for row in rows:
            doc = row[0]  # Např. "DPPO-2025" nebo "DPPO-2025-1" nebo "DPPO-2025-12"

            # Získáme to, co je za základním tvarem
            suffix = doc.replace(base_doklad, "")

            if suffix == "":
                # Pokud existuje čisté "DPPO-2025", bereme to jako index 1
                if max_index < 1: max_index = 1
            elif suffix.startswith("-"):
                # Pokud je tam pomlčka a číslo (např "-2"), zkusíme to převést na číslo
                try:
                    cislo_za_pomlckou = int(suffix[1:])  # Vezme znaky za "-"
                    if cislo_za_pomlckou > max_index:
                        max_index = cislo_za_pomlckou
                except:
                    pass

        # 3. Vytvoříme nové unikátní číslo (Vždy o 1 vyšší než to nejvyšší nalezené)
        novy_index = max_index + 1
        final_doklad = f"{base_doklad}-{novy_index}"

        # 4. Zajistíme existenci účtů
        self.zajisti_existenci_uctu("591", "Daň z příjmů - splatná")
        self.zajisti_existenci_uctu("341", "Daň z příjmů")

        # 5. Vytvoříme novou transakci
        print(f"✅ Vytvářím daňový doklad: {final_doklad}")
        return self.save_transakce(datum, poznamka, final_doklad, "591", "341", vypocena_dan, 0, 'Neučtovat')

    # Wrapper pro staré volání (pro kompatibilitu)
    def provest_uctovani_uzaverky_710(self, datum_uzaverky):
        return self.provest_rocn_uzaverku_komplet(datum_uzaverky.year)

    def provest_rocn_uzaverku_komplet(self, rok):
        """
        Uzavře 5xx/6xx -> 710 a Rozvahu -> 702.
        """
        datum_uzaverky = date(rok, 12, 31)
        datum_od = date(rok, 1, 1)

        # Kontrola existující uzávěrky
        check = execute_query("SELECT id FROM Transakce WHERE doklad_cislo = ? AND klient_id = ?",
                              (f"UZAV-{rok}", self.klient_id))
        if check: return "⚠️ Uzávěrka pro tento rok již existuje. Smažte ji v Historii."

        # A) Zůstatky pro 710 (Výsledovka)
        # Zde používáme P.ucet (string), to je v pořádku
        sql_710 = """
            SELECT P.ucet, SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)
            FROM UcetniPohyby P JOIN Transakce T ON P.transakce_id = T.id
            WHERE T.klient_id = ? AND T.datum >= ? AND T.datum <= ? 
            AND (P.ucet LIKE '5%' OR P.ucet LIKE '6%')
            GROUP BY P.ucet HAVING abs(SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)) > 0.005
        """
        rows_710 = execute_query(sql_710, (self.klient_id, datum_od, datum_uzaverky))

        # B) Zůstatky pro 702 (Rozvaha)
        sql_702 = """
            SELECT P.ucet, SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)
            FROM UcetniPohyby P JOIN Transakce T ON P.transakce_id = T.id
            WHERE T.klient_id = ? AND T.datum <= ? 
            AND (P.ucet LIKE '[0-49]%')
            GROUP BY P.ucet HAVING abs(SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)) > 0.005
        """
        rows_702 = execute_query(sql_702, (self.klient_id, datum_uzaverky))

        if not rows_710 and not rows_702:
            return "⚠️ Žádná data k uzavření."

        # Založení účtů (použije naši opravenou metodu s 'cislo')
        self.zajisti_existenci_uctu("710", "Účet zisků a ztrát")
        self.zajisti_existenci_uctu("702", "Konečný účet rozvažný")

        try:
            with Database() as conn:
                cursor = conn.cursor()

                # Hlavička transakce
                cursor.execute("""
                    INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo, created_at)
                    VALUES (?, ?, ?, ?, GETDATE());
                """, (self.klient_id, datum_uzaverky, f"Uzávěrka roku {rok}", f"UZAV-{rok}"))
                cursor.execute("SELECT SCOPE_IDENTITY()")
                transakce_id = int(cursor.fetchone()[0])

                sql_ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?, ?, ?, ?, ?)"

                hv = 0.0

                # Zpracování 710
                if rows_710:
                    for r in rows_710:
                        ucet, bilance = r[0], float(r[1])
                        if bilance > 0:  # Náklad (MD) -> D
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'D', abs(bilance)))
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'MD', abs(bilance)))
                            hv -= abs(bilance)
                        else:  # Výnos (D) -> MD
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'MD', abs(bilance)))
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'D', abs(bilance)))
                            hv += abs(bilance)

                # Zpracování 702
                if rows_702:
                    for r in rows_702:
                        ucet, bilance = r[0], float(r[1])
                        if bilance > 0:  # Aktivum (MD) -> D
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'D', abs(bilance)))
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'MD', abs(bilance)))
                        else:  # Pasivum (D) -> MD
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'MD', abs(bilance)))
                            cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'D', abs(bilance)))

                # Převod HV (710 -> 702)
                if abs(hv) > 0.005:
                    if hv > 0:  # Zisk (710 D) -> 710 MD / 702 D
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'MD', abs(hv)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'D', abs(hv)))
                    else:  # Ztráta (710 MD) -> 710 D / 702 MD
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'D', abs(hv)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'MD', abs(hv)))

                conn.commit()
                return f"✅ Rok {rok} úspěšně uzavřen! Doklad UZAV-{rok}."

        except Exception as e:
            return f"❌ Chyba při uzávěrce: {e}"

    def otevrit_novy_rok(self, stary_rok):
        nr = stary_rok + 1;
        datum_otevreni = date(nr, 1, 1)

        # Najdeme data z UZAV-{stary_rok}
        sql = "SELECT P.ucet, P.smer, P.castka FROM UcetniPohyby P JOIN Transakce T ON T.id=P.transakce_id WHERE T.doklad_cislo=? AND P.klient_id=? AND P.ucet NOT IN ('702','710')"
        rows = execute_query(sql, (f"UZAV-{stary_rok}", self.klient_id))

        # Najdeme HV z minuleho roku (na uctu 702)
        sqlhv = "SELECT SUM(CASE WHEN P.smer='D' THEN P.castka ELSE -P.castka END) FROM UcetniPohyby P JOIN Transakce T ON T.id=P.transakce_id WHERE T.doklad_cislo=? AND P.ucet='702'"
        reshv = execute_query(sqlhv, (f"UZAV-{stary_rok}", self.klient_id))
        hv = reshv[0][0] if reshv and reshv[0][0] else 0.0

        if not rows and abs(hv) < 0.01: return "⚠️ Nenalezena uzávěrka pro minulý rok."

        self.zajisti_existenci_uctu("701", "Počáteční účet")
        self.zajisti_existenci_uctu("431", "HV ve schvalovacím")

        try:
            with Database() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo, created_at) VALUES (?,?,?,?, GETDATE())",
                    (self.klient_id, datum_otevreni, f"Počátek {nr}", f"POC-{nr}"))
                cur.execute("SELECT SCOPE_IDENTITY()")
                tid = cur.fetchone()[0]
                ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?,?,?,?,?)"

                for r in rows:
                    u = r[0];
                    s = r[1];
                    val = r[2]
                    # Obracíme strany: Co bylo na D (uzavření), jde na MD (otevření)
                    if s == 'D':
                        cur.execute(ins, (tid, self.klient_id, u, 'MD', val))
                        cur.execute(ins, (tid, self.klient_id, '701', 'D', val))
                    else:
                        cur.execute(ins, (tid, self.klient_id, u, 'D', val))
                        cur.execute(ins, (tid, self.klient_id, '701', 'MD', val))

                # Otevření HV (zisk byl na 702 D, ztráta na 702 MD)
                if abs(hv) > 0.005:
                    if hv > 0:  # Zisk -> 431 D
                        cur.execute(ins, (tid, self.klient_id, '431', 'D', abs(hv)))
                        cur.execute(ins, (tid, self.klient_id, '701', 'MD', abs(hv)))
                    else:  # Ztráta -> 431 MD
                        cur.execute(ins, (tid, self.klient_id, '431', 'MD', abs(hv)))
                        cur.execute(ins, (tid, self.klient_id, '701', 'D', abs(hv)))

                conn.commit()
                return f"✅ Otevřeno {nr} (Doklad POC-{nr})."
        except Exception as e:
            return f"Chyba: {e}"
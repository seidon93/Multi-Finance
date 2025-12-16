-- *** 1. ODSTRANĚNÍ EXISTUJÍCÍCH OBJEKTŮ (pro čistou instalaci) ***
-- Drop tabulek, které obsahují cizí klíče na jiné tabulky (child tables)
IF OBJECT_ID('UcetniPohyby') IS NOT NULL DROP TABLE UcetniPohyby;
IF OBJECT_ID('Transakce') IS NOT NULL DROP TABLE Transakce;
IF OBJECT_ID('SazbyDPH') IS NOT NULL DROP TABLE SazbyDPH;
-- Drop mateřských tabulek (parent tables)
IF OBJECT_ID('Klienti') IS NOT NULL DROP TABLE Klienti;
IF OBJECT_ID('UctovyRozvrh') IS NOT NULL DROP TABLE UctovyRozvrh;

-- *** 2. TABULKY A SCHÉMA ***

-- 1. Tabulka Klienti (Základ Multi-tenancy)
CREATE TABLE Klienti (
    id INT PRIMARY KEY IDENTITY(1,1),
    nazev_firmy NVARCHAR(255) NOT NULL,
    ico NVARCHAR(15) UNIQUE,
    datum_registrace DATE
);

-- 4. Tabulka UctovyRozvrh (Účetní Osnova)
CREATE TABLE UctovyRozvrh (
    ucet NVARCHAR(10) PRIMARY KEY,
    nazev NVARCHAR(255) NOT NULL,
    typ_uctu CHAR(1) NOT NULL CHECK (typ_uctu IN ('A', 'P', 'N', 'V', 'S')) -- A=Aktivum, P=Pasivum, N=Náklad, V=Výnos
);

-- 2. Tabulka Transakce (Hlavička Dokladu)
CREATE TABLE Transakce (
    id INT PRIMARY KEY IDENTITY(1,1),
    klient_id INT NOT NULL,
    datum DATE NOT NULL,
    popis NVARCHAR(500),
    doklad_cislo NVARCHAR(50) NOT NULL,
    datum_vytvoreni DATETIME DEFAULT GETDATE(),

    CONSTRAINT FK_Transakce_Klient FOREIGN KEY (klient_id) REFERENCES Klienti(id) ON DELETE CASCADE,
    CONSTRAINT UQ_Doklad_Klient UNIQUE (klient_id, doklad_cislo)
);

-- 3. Tabulka UcetniPohyby (Žurnál)
CREATE TABLE UcetniPohyby (
    id INT PRIMARY KEY IDENTITY(1,1),
    transakce_id INT NOT NULL,
    klient_id INT NOT NULL,
    ucet NVARCHAR(10) NOT NULL,
    smer CHAR(2) NOT NULL CHECK (smer IN ('MD', 'D')),
    castka DECIMAL(18, 2) NOT NULL CHECK (castka >= 0),

    CONSTRAINT FK_Pohyb_Transakce FOREIGN KEY (transakce_id) REFERENCES Transakce(id) ON DELETE CASCADE,
    CONSTRAINT FK_Pohyb_Klient FOREIGN KEY (klient_id) REFERENCES Klienti(id),
    CONSTRAINT FK_Pohyb_Ucet FOREIGN KEY (ucet) REFERENCES UctovyRozvrh(ucet),

    INDEX IX_UcetniPohyby_Ucet (klient_id, ucet)
);

-- 5. Tabulka SazbyDPH
CREATE TABLE SazbyDPH (
    sazba_id INT PRIMARY KEY IDENTITY(1,1),
    procento DECIMAL(5, 2) NOT NULL UNIQUE,
    typ_dph NVARCHAR(50) NOT NULL,
    ucet_dph_vstup NVARCHAR(10) NOT NULL,
    ucet_dph_vystup NVARCHAR(10) NOT NULL,

    CONSTRAINT FK_DPH_Vstup FOREIGN KEY (ucet_dph_vstup) REFERENCES UctovyRozvrh(ucet),
    CONSTRAINT FK_DPH_Vystup FOREIGN KEY (ucet_dph_vystup) REFERENCES UctovyRozvrh(ucet)
);


-- *** 3. INICIALIZAČNÍ DATA (OPRAVENO) ***

-- 1. Naplnění Klientů
SET IDENTITY_INSERT Klienti ON;
INSERT INTO Klienti (id, nazev_firmy, ico) VALUES (1, 'Demo Klient', '12345678');
SET IDENTITY_INSERT Klienti OFF;

-- 2. Naplnění UctovyRozvrh (MUSÍ OBSAHOVAT VŠECHNY ÚČTY POUŽITÉ V SAZBÁCH DPH)
INSERT INTO UctovyRozvrh (ucet, nazev, typ_uctu) VALUES
-- Základní účty
('211', 'Pokladna', 'A'),
('221', 'Běžný bankovní účet', 'A'),
('311', 'Pohledávky za odběrateli', 'A'),
('321', 'Závazky vůči dodavatelům', 'P'),
('511', 'Opravy a udržování', 'N'),
('501', 'Spotřeba materiálu', 'N'),
('518', 'Ostatní služby', 'N'),
('602', 'Tržby za služby', 'V'),

-- DPH Analytika (Musí přesně sedět na to, co je v SazbyDPH)
-- 21%
('343.1.21', 'DPH na vstupu (21%)', 'A'),
('343.2.21', 'DPH na výstupu (21%)', 'P'),
-- 12%
('343.1.12', 'DPH na vstupu (12%)', 'A'),
('343.2.12', 'DPH na výstupu (12%)', 'P'),
-- 0% / Osvobozeno / Přenesená daň
('343.1.00', 'DPH na vstupu (0%)', 'A'),
('343.2.00', 'DPH na výstupu (0%)', 'P');

-- 3. Naplnění SazbyDPH (Teď už to projde, protože účty existují)
INSERT INTO SazbyDPH (procento, typ_dph, ucet_dph_vstup, ucet_dph_vystup) VALUES
(21.00, 'Standardní', '343.1.21', '343.2.21'),
(12.00, 'Snížená',    '343.1.12', '343.2.12'),
(0.00,  'Osvobozeno', '343.1.00', '343.2.00');
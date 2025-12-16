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
-- Musí být vytvořena před Transakcemi, protože Transakce na ni odkazují.
CREATE TABLE UctovyRozvrh (
    ucet NVARCHAR(10) PRIMARY KEY,
    nazev NVARCHAR(255) NOT NULL,
    typ_uctu CHAR(1) NOT NULL CHECK (typ_uctu IN ('A', 'P', 'N', 'V', 'S'))
);

-- 2. Tabulka Transakce (Hlavička Dokladu)
-- Tato tabulka obsahuje pouze informace o dokladu a referenci na účetní pohyby.
-- ZÁMĚRNĚ BYLA ODSTRANĚNA DUPLICITNÍ ÚČETNÍ POLE ucet_MD, ucet_DAL, castka
-- Tyto informace se efektivně ukládají POUZE v UcetniPohyby.
CREATE TABLE Transakce (
    id INT PRIMARY KEY IDENTITY(1,1),

    -- Cizí Klíč pro Multi-tenancy
    klient_id INT NOT NULL,
    CONSTRAINT FK_Transakce_Klient
        FOREIGN KEY (klient_id) REFERENCES Klienti(id)
        ON DELETE CASCADE,

    datum DATE NOT NULL,
    popis NVARCHAR(500),
    doklad_cislo NVARCHAR(50) NOT NULL,
    datum_vytvoreni DATETIME DEFAULT GETDATE(),

    -- Unikátnost dokladu v rámci jednoho klienta
    CONSTRAINT UQ_Doklad_Klient UNIQUE (klient_id, doklad_cislo) -- Přidáno pro zamezení duplicit
);

-- 3. Tabulka UcetniPohyby (Žurnál - Srdce Účetnictví)
-- Zde se ukládá každý MD a D pohyb samostatně (jedna transakce = dva pohyby/řádky).
CREATE TABLE UcetniPohyby (
    id INT PRIMARY KEY IDENTITY(1,1),

    transakce_id INT NOT NULL,
    CONSTRAINT FK_Pohyb_Transakce
        FOREIGN KEY (transakce_id) REFERENCES Transakce(id)
        ON DELETE CASCADE,

    klient_id INT NOT NULL, 
    CONSTRAINT FK_Pohyb_Klient
        FOREIGN KEY (klient_id) REFERENCES Klienti(id),

    ucet NVARCHAR(10) NOT NULL,
    CONSTRAINT FK_Pohyb_Ucet FOREIGN KEY (ucet) REFERENCES UctovyRozvrh(ucet), -- Odkaz na účet

    smer CHAR(2) NOT NULL CHECK (smer IN ('MD', 'D')),
    castka DECIMAL(18, 2) NOT NULL CHECK (castka >= 0),

    INDEX IX_UcetniPohyby_Ucet (klient_id, ucet)
);

-- 5. Tabulka SazbyDPH
CREATE TABLE SazbyDPH (
    sazba_id INT PRIMARY KEY IDENTITY(1,1),
    procento DECIMAL(5, 2) NOT NULL UNIQUE, -- Např. 21.00
    typ_dph NVARCHAR(50) NOT NULL,          -- Např. 'Standardní', 'Snížená'
    ucet_dph_vstup NVARCHAR(10) NOT NULL,   -- Účet pro DPH na vstupu (např. 343.1)
    ucet_dph_vystup NVARCHAR(10) NOT NULL,  -- Účet pro DPH na výstupu (např. 343.2)

    CONSTRAINT FK_DPH_Vstup FOREIGN KEY (ucet_dph_vstup) REFERENCES UctovyRozvrh(ucet),
    CONSTRAINT FK_DPH_Vystup FOREIGN KEY (ucet_dph_vystup) REFERENCES UctovyRozvrh(ucet)
);


-- *** 3. INICIALIZAČNÍ DATA ***

-- Naplnění UctovyRozvrh
INSERT INTO UctovyRozvrh (ucet, nazev, typ_uctu) VALUES
('221', 'Běžný bankovní účet', 'A'),
('311', 'Pohledávky za odběrateli', 'A'),
('343.1.12', 'Daň z přidané hodnoty', 'P'),
('321', 'Závazky vůči dodavatelům', 'P'),
('511', 'Opravy a udržování', 'N'),
('602', 'Tržby za služby', 'V');

INSERT INTO UctovyRozvrh (ucet, nazev, typ_uctu) VALUES
('343.1', 'DPH na vstupu (Pohledávka)', 'A'),
('343.2', 'DPH na výstupu (Závazek)', 'P');

INSERT INTO SazbyDPH (procento, typ_dph, ucet_dph_vstup, ucet_dph_vystup) VALUES
(21.00, 'Standardní', '343.1.21', '343.2.21'),
(12.00, 'Snížená', '343.1.12', '343.2.12'),
(0.00, 'Osvobozeno', '343.1.00', '343.2.00');

-- Naplnění Klienti (Multi-tenancy základ)
SET IDENTITY_INSERT Klienti ON;
INSERT INTO Klienti (id, nazev_firmy, ico)
VALUES (1, 'Demo Klient', '12345678');
SET IDENTITY_INSERT Klienti OFF;
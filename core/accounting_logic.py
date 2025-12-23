from collections import defaultdict
from core.database import execute_query, Database
from decimal import Decimal
from datetime import date, datetime
import pandas as pd
import os
import streamlit as st

# --- MAPOVÁNÍ ÚČTŮ (SYNTETIKY) ---
MAPOVANI_AKTIV_FULL = {
    "02": ["353"], "05": ["011"], "07": ["013"], "08": ["012", "014", "019"],
    "09": ["015"], "10": ["019"], "12": ["051"], "13": ["041"], "16": ["031"],
    "17": ["021"], "18": ["022"], "19": ["097"], "21": ["025"], "22": ["026"],
    "23": ["029"], "25": ["052"], "26": ["042"], "28": ["061"], "29": ["066"],
    "30": ["062"], "31": ["068"], "32": ["063", "065"], "33": ["067", "069"],
    "35": ["069"], "36": ["053"], "39": ["112", "111"], "40": ["121", "122"],
    "42": ["123"], "43": ["132"], "44": ["124"], "45": ["151", "152", "153"],
    "48": ["311"], "49": ["351"], "50": ["352"], "51": ["481"], "53": ["354", "355"],
    "54": ["314"], "55": ["388"], "56": ["371", "378"], "58": ["311"], "59": ["351"],
    "60": ["352"], "62": ["354", "355"], "63": ["336"], "64": ["343", "345", "349"],
    "65": ["314"], "66": ["388"], "67": ["371", "378"], "69": ["381"], "70": ["382"],
    "71": ["385"], "73": ["251", "252"], "74": ["253", "256", "257"], "76": ["211"],
    "77": ["221"], "79": ["381"], "80": ["382"], "81": ["385"]
}

# --- ŠABLONY TISKOPISŮ ---
SABLONA_AKTIVA_FULL = [
    {"ozn": "", "n": "AKTIVA CELKEM (A+B+C+D)", "r": "01", "bold": True},
    {"ozn": "A.", "n": "Pohledávky za upsaný základní kapitál", "r": "02", "bold": False},
    {"ozn": "B.", "n": "Stálá aktiva (B.I. + B.II. + B.III.)", "r": "03", "bold": True},
    {"ozn": "B.I.", "n": "Dlouhodobý nehmotný majetek (součet B.I.1. až B.I.5.2.)", "r": "04", "bold": True},
    {"ozn": "1.", "n": "Nehmotné výsledky vývoje", "r": "05", "bold": False},
    {"ozn": "2.", "n": "Ocenitelná práva", "r": "06", "bold": True},
    {"ozn": "2.1.", "n": "Software", "r": "07", "bold": False},
    {"ozn": "2.2.", "n": "Ostatní ocenitelná práva", "r": "08", "bold": False},
    {"ozn": "3.", "n": "Goodwill", "r": "09", "bold": False},
    {"ozn": "4.", "n": "Ostatní dlouhodobý nehmotný majetek", "r": "10", "bold": False},
    {"ozn": "5.", "n": "Poskytnuté zálohy a nedokončený nehmotný majetek", "r": "11", "bold": True},
    {"ozn": "5.1.", "n": "Poskytnuté zálohy na dlouhodobý nehmotný majetek", "r": "12", "bold": False},
    {"ozn": "5.2.", "n": "Nedokončený dlouhodobý nehmotný majetek", "r": "13", "bold": False},
    {"ozn": "B.II.", "n": "Dlouhodobý hmotný majetek (součet B.II.1. až B.II.5.2.)", "r": "14", "bold": True},
    {"ozn": "1.", "n": "Pozemky a stavby", "r": "15", "bold": True},
    {"ozn": "1.1.", "n": "Pozemky", "r": "16", "bold": False},
    {"ozn": "1.2.", "n": "Stavby", "r": "17", "bold": False},
    {"ozn": "2.", "n": "Hmotné movité věci a jejich soubory", "r": "18", "bold": False},
    {"ozn": "3.", "n": "Oceňovací rozdíl k nabytému majetku", "r": "19", "bold": False},
    {"ozn": "4.", "n": "Ostatní dlouhodobý hmotný majetek", "r": "20", "bold": True},
    {"ozn": "4.1.", "n": "Pěstitelské celky trvalých porostů", "r": "21", "bold": False},
    {"ozn": "4.2.", "n": "Dospělá zvířata a jejich skupiny", "r": "22", "bold": False},
    {"ozn": "4.3.", "n": "Jiný dlouhodobý hmotný majetek", "r": "23", "bold": False},
    {"ozn": "5.", "n": "Poskytnuté zálohy a nedokončený hmotný majetek", "r": "24", "bold": True},
    {"ozn": "5.1.", "n": "Poskytnuté zálohy na dlouhodobý hmotný majetek", "r": "25", "bold": False},
    {"ozn": "5.2.", "n": "Nedokončený dlouhodobý hmotný majetek", "r": "26", "bold": False},
    {"ozn": "B.III.", "n": "Dlouhodobý finanční majetek (součet B.III.1. až B.III.7.2.)", "r": "27", "bold": True},
    {"ozn": "1.", "n": "Podíly – ovládaná nebo ovládající osoba", "r": "28", "bold": False},
    {"ozn": "2.", "n": "Zápůjčky a úvěry – ovládaná nebo ovládající osoba", "r": "29", "bold": False},
    {"ozn": "3.", "n": "Podíly – podstatný vliv", "r": "30", "bold": False},
    {"ozn": "4.", "n": "Zápůjčky a úvěry – podstatný vliv", "r": "31", "bold": False},
    {"ozn": "5.", "n": "Ostatní dlouhodobé cenné papíry a podíly", "r": "32", "bold": False},
    {"ozn": "6.", "n": "Zápůjčky a úvěry - ostatní", "r": "33", "bold": False},
    {"ozn": "7.", "n": "Ostatní dlouhodobý finanční majetek", "r": "34", "bold": True},
    {"ozn": "7.1.", "n": "Jiný dlouhodobý finanční majetek", "r": "35", "bold": False},
    {"ozn": "7.2.", "n": "Poskytnuté zálohy na dlouhodobý finanční majetek", "r": "36", "bold": False},
    {"ozn": "C.", "n": "Oběžná aktiva (C.I. + C.II. + C.III. + C.IV.)", "r": "37", "bold": True},
    {"ozn": "C.I.", "n": "Zásoby (součet C. I.1. až C.I.5.)", "r": "38", "bold": True},
    {"ozn": "1.", "n": "Materiál", "r": "39", "bold": False},
    {"ozn": "2.", "n": "Nedokončená výroba a polotovary", "r": "40", "bold": False},
    {"ozn": "3.", "n": "Výrobky a zboží", "r": "41", "bold": True},
    {"ozn": "3.1.", "n": "Výrobky", "r": "42", "bold": False},
    {"ozn": "3.2.", "n": "Zboží", "r": "43", "bold": False},
    {"ozn": "4.", "n": "Mladá a ostatní zvířata a jejich skupiny", "r": "44", "bold": False},
    {"ozn": "5.", "n": "Poskytnuté zálohy na zásoby", "r": "45", "bold": False},
    {"ozn": "C.II.", "n": "Pohledávky (C.II.1 + C.II.2 + C.II.3)", "r": "46", "bold": True},
    {"ozn": "1.", "n": "Dlouhodobé pohledávky", "r": "47", "bold": True},
    {"ozn": "1.1.", "n": "Pohledávky z obchodních vztahů", "r": "48", "bold": False},
    {"ozn": "1.2.", "n": "Pohledávky – ovládaná nebo ovládající osoba", "r": "49", "bold": False},
    {"ozn": "1.3.", "n": "Pohledávky – podstatný vliv", "r": "50", "bold": False},
    {"ozn": "1.4.", "n": "Odložená daňová pohledávka", "r": "51", "bold": False},
    {"ozn": "1.5.", "n": "Pohledávky - ostatní", "r": "52", "bold": True},
    {"ozn": "5.1.", "n": "Pohledávky za společníky", "r": "53", "bold": False},
    {"ozn": "5.2.", "n": "Dlouhodobé poskytnuté zálohy", "r": "54", "bold": False},
    {"ozn": "5.3.", "n": "Dohadné účty aktivní", "r": "55", "bold": False},
    {"ozn": "5.4.", "n": "Jiné pohledávky", "r": "56", "bold": False},
    {"ozn": "2.", "n": "Krátkodobé pohledávky", "r": "57", "bold": True},
    {"ozn": "2.1.", "n": "Pohledávky z obchodních vztahů", "r": "58", "bold": False},
    {"ozn": "2.2.", "n": "Pohledávky – ovládaná nebo ovládající osoba", "r": "59", "bold": False},
    {"ozn": "2.3.", "n": "Pohledávky – podstatný vliv", "r": "60", "bold": False},
    {"ozn": "2.4.", "n": "Pohledávky - ostatní", "r": "61", "bold": True},
    {"ozn": "4.1.", "n": "Pohledávky za společníky", "r": "62", "bold": False},
    {"ozn": "4.2.", "n": "Sociální zabezpečení a zdravotní pojištění", "r": "63", "bold": False},
    {"ozn": "4.3.", "n": "Stát - daňové pohledávky", "r": "64", "bold": False},
    {"ozn": "4.4.", "n": "Krátkodobé poskytnuté zálohy", "r": "65", "bold": False},
    {"ozn": "4.5.", "n": "Dohadné účty aktivní", "r": "66", "bold": False},
    {"ozn": "4.6.", "n": "Jiné pohledávky", "r": "67", "bold": False},
    {"ozn": "3.", "n": "Časové rozlišení aktiv", "r": "68", "bold": True},
    {"ozn": "3.1.", "n": "Náklady příštích období", "r": "69", "bold": False},
    {"ozn": "3.2.", "n": "Komplexní náklady příštích období", "r": "70", "bold": False},
    {"ozn": "3.3.", "n": "Příjmy příštích období", "r": "71", "bold": False},
    {"ozn": "C.III.", "n": "Krátkodobý finanční majetek (C.III.1. + C.III.2.)", "r": "72", "bold": True},
    {"ozn": "1.", "n": "Podíly – ovládaná nebo ovládající osoba", "r": "73", "bold": False},
    {"ozn": "2.", "n": "Ostatní krátkodobý finanční majetek", "r": "74", "bold": False},
    {"ozn": "C.IV.", "n": "Peněžní prostředky (C.IV.1. + C.IV.2.)", "r": "75", "bold": True},
    {"ozn": "1.", "n": "Peněžní prostředky v pokladně", "r": "76", "bold": False},
    {"ozn": "2.", "n": "Peněžní prostředky na účtech", "r": "77", "bold": False},
    {"ozn": "D.", "n": "Časové rozlišení aktiv (D.1. + D.2.+ D.3.)", "r": "78", "bold": True},
    {"ozn": "1.", "n": "Náklady příštích období", "r": "79", "bold": False},
    {"ozn": "2.", "n": "Komplexní náklady příštích období", "r": "80", "bold": False},
    {"ozn": "3.", "n": "Příjmy příštích období", "r": "81", "bold": False},
]

# Mapování pro Pasiva - propojení čísel řádků na účetní třídy 3 a 4
MAPOVANI_PASIVA_FULL = {
    "04": ["411"],       # Základní kapitál
    "05": ["252"],       # Vlastní podíly (-)
    "06": ["419"],       # Změny základního kapitálu
    "08": ["412"],       # Ážio
    "10": ["413"],       # Ostatní kapitálové fondy
    "11": ["414"],       # Oceňovací rozdíly z přecenění majetku a závazků
    "12": ["418"],       # Oceňovací rozdíly při přeměnách
    "13": ["417"],       # Rozdíly z přeměn
    "14": ["416"],       # Rozdíly z ocenění při přeměnách
    "16": ["421"],       # Ostatní rezervní fondy
    "17": ["423", "427"], # Statutární a ostatní fondy
    "19": ["428", "429"], # Nerozdělený zisk / neuhrazená ztráta minulých let
    "22": ["432"],       # Rozhodnuto o zálohové výplatě podílu na zisku (-)
    "25": ["451"],       # Rezerva na důchody a podobné závazky
    "26": ["453"],       # Rezerva na daň z příjmů
    "27": ["451"],       # Rezervy podle zvláštních právních předpisů
    "28": ["459"],       # Ostatní rezervy
    "31": ["473"],       # Vydané dluhopisy (dlouhodobé)
    "34": ["461"],       # Závazky k úvěrovým institucím (dlouhodobé)
    "35": ["475"],       # Dlouhodobé přijaté zálohy
    "37": ["478"],       # Dlouhodobé směnky k úhradě
    "38": ["471"],       # Závazky - ovládaná nebo ovládající osoba
    "39": ["472"],       # Závazky - podstatný vliv
    "40": ["481"],       # Odložený daňový závazek
    "42": ["361", "364", "365", "366", "367", "368"], # Závazky ke společníkům (dlouhodobé)
    "43": ["389"],       # Dohadné účty pasivní (dlouhodobé)
    "44": ["479"],       # Jiné závazky (dlouhodobé)
    "46": ["241"],       # Vydané dluhopisy (krátkodobé)
    "49": ["231"],       # Závazky k úvěrovým institucím (krátkodobé)
    "50": ["324"],       # Krátkodobé přijaté zálohy
    "51": ["321"],       # Závazky z obchodních vztahů
    "52": ["322"],       # Krátkodobé směnky k úhradě
    "53": ["361"],       # Závazky - ovládaná nebo ovládající osoba
    "54": ["362"],       # Závazky - podstatný vliv
    "56": ["364", "365"], # Závazky ke společníkům (krátkodobé)
    "57": ["249"],       # Krátkodobé finanční výpomoci
    "58": ["331"],       # Závazky k zaměstnancům
    "59": ["336"],       # Závazky ze sociálního a zdravotního pojištění
    "60": ["341", "342", "343", "345"], # Stát - daňové závazky a dotace
    "61": ["389"],       # Dohadné účty pasivní (krátkodobé)
    "62": ["379"],       # Jiné závazky (krátkodobé)
    "67": ["383"],       # Výdaje příštích období
    "68": ["384"],       # Výnosy příštích období
}

# Kompletní skelet Pasiv
SABLONA_PASIVA_FULL = [
    {"ozn": "", "n": "PASIVA CELKEM (A. + B. + C. + D.)", "r": "01", "bold": True},
    {"ozn": "A.", "n": "Vlastní kapitál", "r": "02", "bold": True},
    {"ozn": "A.I.", "n": "Základní kapitál", "r": "03", "bold": True},
    {"ozn": "1.", "n": "Základní kapitál", "r": "04", "bold": False},
    {"ozn": "2.", "n": "Vlastní podíly (-)", "r": "05", "bold": False},
    {"ozn": "3.", "n": "Změny základního kapitálu", "r": "06", "bold": False},
    {"ozn": "A.II.", "n": "Ážio a kapitálové fondy", "r": "07", "bold": True},
    {"ozn": "1.", "n": "Ážio", "r": "08", "bold": False},
    {"ozn": "2.", "n": "Kapitálové fondy", "r": "09", "bold": True},
    {"ozn": "2.2.", "n": "Oceňovací rozdíly z přecenění majetku a závazků (+/-)", "r": "11", "bold": False},
    {"ozn": "2.3.", "n": "Oceňovací rozdíly z přecenění při přeměnách (+/-)", "r": "12", "bold": False},
    {"ozn": "2.4.", "n": "Rozdíly z přeměn obchodních korporací (+/-)", "r": "13", "bold": False},
    {"ozn": "2.5.", "n": "Rozdíly z ocenění při přeměnách (+/-)", "r": "14", "bold": False},
    {"ozn": "A.III.", "n": "Fondy ze zisku", "r": "15", "bold": True},
    {"ozn": "1.", "n": "Ostatní rezervní fondy", "r": "16", "bold": False},
    {"ozn": "2.", "n": "Statutární a ostatní fondy", "r": "17", "bold": False},
    {"ozn": "A.IV.", "n": "Výsledek hospodaření minulých let (+/-)", "r": "18", "bold": True},
    {"ozn": "1.", "n": "Nerozdělený zisk nebo neuhrazená ztráta minulých let (+/-)", "r": "19", "bold": False},
    {"ozn": "A.V.", "n": "Výsledek hospodaření běžného účetního období (+/-)", "r": "21", "bold": False},
    {"ozn": "A.VI.", "n": "Rozhodnuto o zálohové výplatě podílu na zisku (-)", "r": "22", "bold": False},
    {"ozn": "B + C.", "n": "Cizí zdroje (součet B. + C.)", "r": "23", "bold": True},
    {"ozn": "B.", "n": "Rezervy (součet B.1. až B.4.)", "r": "24", "bold": True},
    {"ozn": "1.", "n": "Rezerva na důchody a podobné závazky", "r": "25", "bold": False},
    {"ozn": "2.", "n": "Rezerva na daň z příjmů", "r": "26", "bold": False},
    {"ozn": "3.", "n": "Rezervy podle zvláštních právních předpisů", "r": "27", "bold": False},
    {"ozn": "4.", "n": "Ostatní rezervy", "r": "28", "bold": False},
    {"ozn": "C.", "n": "Závazky (součet C.I. + C.II. + C.III.)", "r": "29", "bold": True},
    {"ozn": "C.I.", "n": "Dlouhodobé závazky", "r": "30", "bold": True},
    {"ozn": "1.", "n": "Vydané dluhopisy", "r": "31", "bold": True},
    {"ozn": "1.1.", "n": "Vyměnitelné dluhopisy", "r": "32", "bold": False},
    {"ozn": "1.2.", "n": "Ostatní dluhopisy", "r": "33", "bold": False},
    {"ozn": "2.", "n": "Závazky k úvěrovým institucím", "r": "34", "bold": False},
    {"ozn": "3.", "n": "Dlouhodobé přijaté zálohy", "r": "35", "bold": False},
    {"ozn": "5.", "n": "Dlouhodobé směnky k úhradě", "r": "37", "bold": False},
    {"ozn": "6.", "n": "Závazky - ovládaná nebo ovládající osoba", "r": "38", "bold": False},
    {"ozn": "7.", "n": "Závazky - podstatný vliv", "r": "39", "bold": False},
    {"ozn": "8.", "n": "Odložený daňový závazek", "r": "40", "bold": False},
    {"ozn": "9.", "n": "Závazky - ostatní", "r": "41", "bold": True},
    {"ozn": "9.1.", "n": "Závazky ke společníkům", "r": "42", "bold": False},
    {"ozn": "9.2.", "n": "Dohadné účty pasivní", "r": "43", "bold": False},
    {"ozn": "9.3.", "n": "Jiné závazky", "r": "44", "bold": False},
    {"ozn": "C.II.", "n": "Krátkodobé závazky", "r": "45", "bold": True},
    {"ozn": "1.", "n": "Vydané dluhopisy", "r": "46", "bold": True},
    {"ozn": "1.1.", "n": "Vyměnitelné dluhopisy", "r": "47", "bold": False},
    {"ozn": "1.2.", "n": "Ostatní dluhopisy", "r": "48", "bold": False},
    {"ozn": "2.", "n": "Závazky k úvěrovým institucím", "r": "49", "bold": False},
    {"ozn": "3.", "n": "Krátkodobé přijaté zálohy", "r": "50", "bold": False},
    {"ozn": "5.", "n": "Krátkodobé směnky k úhradě", "r": "52", "bold": False},
    {"ozn": "6.", "n": "Závazky - ovládaná nebo ovládající osoba", "r": "53", "bold": False},
    {"ozn": "7.", "n": "Závazky - podstatný vliv", "r": "54", "bold": False},
    {"ozn": "8.", "n": "Závazky ostatní", "r": "55", "bold": True},
    {"ozn": "8.1.", "n": "Závazky ke společníkům", "r": "56", "bold": False},
    {"ozn": "8.2.", "n": "Krátkodobé finanční výpomoci", "r": "57", "bold": False},
    {"ozn": "8.6.", "n": "Dohadné účty pasivní", "r": "61", "bold": False},
    {"ozn": "8.7.", "n": "Jiné závazky", "r": "62", "bold": False},
    {"ozn": "D.", "n": "Časové rozlišení pasiv", "r": "66", "bold": True},
    {"ozn": "1.", "n": "Výdaje příštích období", "r": "67", "bold": False},
    {"ozn": "2.", "n": "Výnosy příštích období", "r": "68", "bold": False},
]

# Mapování pro Výsledovku - propojení na výnosové a nákladové účty
MAPOVANI_VYSLEDOVKY_FULL = {
    "01": ["601", "602"], "02": ["604"], "04": ["504"], "05": ["501", "502", "503"],
    "06": ["511", "512", "513", "518"], "07": ["581", "582", "583", "584"],
    "08": ["585", "586", "587", "588"], "10": ["521", "522", "523"],
    "12": ["524"], "13": ["525", "527", "528"], "15": ["551"], "18": ["559"],
    "19": ["558"], "21": ["641"], "22": ["642"], "23": ["644", "646", "648"],
    "25": ["541"], "26": ["542"], "27": ["531", "532", "538"],
    "28": ["552", "554", "555"], "29": ["543", "544", "545", "546", "547", "549"],
    "32": ["665"], "33": ["665"], "34": ["561"], "36": ["666"], "37": ["666"],
    "38": ["566"], "40": ["662"], "41": ["662"], "42": ["574", "579"],
    "44": ["562"], "45": ["562"], "46": ["663", "668"], "47": ["563", "568"],
    "51": ["591", "595"], "52": ["592"], "54": ["596"]
}

# --- SKELET VÝSLEDOVKY (56 řádků) ---
SABLONA_VYSLEDOVKA_FULL = [
    {"ozn": "I.", "n": "Tržby z prodeje výrobků a služeb", "r": "01", "bold": False},
    {"ozn": "II.", "n": "Tržby za prodej zboží", "r": "02", "bold": False},
    {"ozn": "A.", "n": "Výkonová spotřeba (součet A.1. až A.3.)", "r": "03", "bold": True},
    {"ozn": "A.1.", "n": "Náklady vynaložené na prodané zboží", "r": "04", "bold": False},
    {"ozn": "2.", "n": "Spotřeba materiálu a energie", "r": "05", "bold": False},
    {"ozn": "3.", "n": "Služby", "r": "06", "bold": False},
    {"ozn": "B.", "n": "Změna stavu zásob vlastní činnosti (+/-)", "r": "07", "bold": False},
    {"ozn": "C.", "n": "Aktivace (-)", "r": "08", "bold": False},
    {"ozn": "D.", "n": "Osobní náklady (součet D.1. až D.2.)", "r": "09", "bold": True},
    {"ozn": "D.1.", "n": "Mzdové náklady", "r": "10", "bold": False},
    {"ozn": "2.", "n": "Náklady na sociální zabezpečení a ostatní náklady", "r": "11", "bold": True},
    {"ozn": "2.1.", "n": "Náklady na sociální zabezpečení a pojištění", "r": "12", "bold": False},
    {"ozn": "2.2.", "n": "Ostatní náklady", "r": "13", "bold": False},
    {"ozn": "E.", "n": "Úpravy hodnot v provozní oblasti (součet E.1. až E.3.)", "r": "14", "bold": True},
    {"ozn": "E.1.", "n": "Úpravy hodnot DNM a DHM", "r": "15", "bold": True},
    {"ozn": "1.1.", "n": "Úpravy hodnot DNM a DHM - trvalé", "r": "16", "bold": False},
    {"ozn": "1.2.", "n": "Úpravy hodnot DNM a DHM - dočasné", "r": "17", "bold": False},
    {"ozn": "2.", "n": "Úpravy hodnot zásob", "r": "18", "bold": False},
    {"ozn": "3.", "n": "Úpravy hodnot pohledávek", "r": "19", "bold": False},
    {"ozn": "III.", "n": "Ostatní provozní výnosy (součet III.1 až III.3.)", "r": "20", "bold": True},
    {"ozn": "1.", "n": "Tržby z prodaného dlouhodobého majetku", "r": "21", "bold": False},
    {"ozn": "2.", "n": "Tržby z prodaného materiálu", "r": "22", "bold": False},
    {"ozn": "3.", "n": "Jiné provozní výnosy", "r": "23", "bold": False},
    {"ozn": "F.", "n": "Ostatní provozní náklady (součet F.1. až F.5.)", "r": "24", "bold": True},
    {"ozn": "F.1.", "n": "Zůstatková cena prodaného dlouhodobého majetku", "r": "25", "bold": False},
    {"ozn": "2.", "n": "Prodaný materiál", "r": "26", "bold": False},
    {"ozn": "3.", "n": "Daně a poplatky", "r": "27", "bold": False},
    {"ozn": "4.", "n": "Rezervy a komplexní náklady", "r": "28", "bold": False},
    {"ozn": "5.", "n": "Jiné provozní náklady", "r": "29", "bold": False},
    {"ozn": "*", "n": "Provozní výsledek hospodaření (+/-)", "r": "30", "bold": True},
    {"ozn": "IV.", "n": "Výnosy z podílů (součet IV. 1 + IV.2.)", "r": "31", "bold": True},
    {"ozn": "1.", "n": "Výnosy z podílů – ovládaná osoba", "r": "32", "bold": False},
    {"ozn": "2.", "n": "Ostatní výnosy z podílů", "r": "33", "bold": False},
    {"ozn": "G.", "n": "Náklady vynaložené na prodané podíly", "r": "34", "bold": False},
    {"ozn": "V.", "n": "Výnosy z ostatního finančního majetku", "r": "35", "bold": True},
    {"ozn": "1.", "n": "Výnosy z finančního majetku - ovládaná osoba", "r": "36", "bold": False},
    {"ozn": "2.", "n": "Ostatní výnosy z finančního majetku", "r": "37", "bold": False},
    {"ozn": "H.", "n": "Náklady související s finančním majetkem", "r": "38", "bold": False},
    {"ozn": "VI.", "n": "Výnosové úroky (součet VI. 1 + VI.2.)", "r": "39", "bold": True},
    {"ozn": "1.", "n": "Výnosové úroky – ovládaná osoba", "r": "40", "bold": False},
    {"ozn": "2.", "n": "Ostatní výnosové úroky", "r": "41", "bold": False},
    {"ozn": "I.", "n": "Úpravy hodnot a rezervy ve finanční oblasti", "r": "42", "bold": False},
    {"ozn": "J.", "n": "Nákladové úroky (součet J.1 + J.2.)", "r": "43", "bold": True},
    {"ozn": "J.1.", "n": "Nákladové úroky - ovládaná osoba", "r": "44", "bold": False},
    {"ozn": "2.", "n": "Ostatní nákladové úroky", "r": "45", "bold": False},
    {"ozn": "VII.", "n": "Ostatní finanční výnosy", "r": "46", "bold": False},
    {"ozn": "K.", "n": "Ostatní finanční náklady", "r": "47", "bold": False},
    {"ozn": "*", "n": "Finanční výsledek hospodaření (+/-)", "r": "48", "bold": True},
    {"ozn": "**", "n": "Výsledek hospodaření před zdaněním (+/-)", "r": "49", "bold": True},
    {"ozn": "L.", "n": "Daň z příjmů (součet L. 1 + L.2.)", "r": "50", "bold": True},
    {"ozn": "L.1.", "n": "Daň z příjmů splatná", "r": "51", "bold": False},
    {"ozn": "2.", "n": "Daň z příjmů odložená (+/-)", "r": "52", "bold": False},
    {"ozn": "**", "n": "Výsledek hospodaření po zdanění (+/-)", "r": "53", "bold": True},
    {"ozn": "M.", "n": "Převod podílu na VH společníkům (+/-)", "r": "54", "bold": False},
    {"ozn": "***", "n": "Výsledek hospodaření za účetní období (+/-)", "r": "55", "bold": True},
    {"ozn": "", "n": "Čistý obrat za účetní období", "r": "56", "bold": True}
]

# --- MAPOVÁNÍ CASH FLOW ---
MAPOVANI_CF_FULL = {
    "P": ["211", "221", "213"],   # Začátek období
    "A11": ["551"],               # Odpisy (+)
    "A12": ["552", "554", "559"], # Změna rezerv a OP
    "A14": ["665"],               # Výnosy z podílů (-)
    "A15": ["562", "662"],        # Nákladové a výnosové úroky
    "A21": ["311", "315", "378"], # Pohledávky
    "A22": ["321", "325", "379"], # Závazky
    "A23": ["112", "123", "132"], # Zásoby
    "A24": ["251", "253"],        # Krátkodobý fin. majetek
    "B1": ["041", "042"],         # Výdaje na stálá aktiva
    "B2": ["641"],                # Příjmy z prodeje majetku
    "C21": ["411"],               # Zvýšení zákl. kapitálu
    "C26": ["432", "364"],        # Vyplacené dividendy (-)
    "R": ["211", "221", "213"]    # Konec období
}

# --- SKELET CASH FLOW (DLE VAŠEHO SEZNAMU) ---
SABLONA_CF_FULL = [
    {"ozn": "P.", "n": "Stav peněžních prostředků (PP) na začátku účetního období", "r": "", "bold": True},
    {"ozn": "", "n": "PENĚŽNÍ TOKY Z PROVOZNÍ ČINNOSTI", "r": "", "bold": True},
    {"ozn": "Z.", "n": "Účetní zisk nebo ztráta před zdaněním", "r": "01", "bold": False},
    {"ozn": "A.1.", "n": "Úprava o nepeněžní operace", "r": "02", "bold": True},
    {"ozn": "A.1.1.", "n": "Odpisy stálých aktiv (+)", "r": "03", "bold": False},
    {"ozn": "A.1.2.", "n": "Změna stavu opravných položek, rezerv", "r": "04", "bold": False},
    {"ozn": "A.1.3.", "n": "Zisk (ztráta) z prodeje stálých aktiv (+/-)", "r": "05", "bold": False},
    {"ozn": "A.1.4.", "n": "Výnosy z dividend a podílů na zisku (-)", "r": "06", "bold": False},
    {"ozn": "A.1.5.", "n": "Vyúčtované nákladové a výnosové úroky (+/-)", "r": "07", "bold": False},
    {"ozn": "A.*", "n": "Čistý peněžní tok z provozní činnosti před zdaněním a změnami PK", "r": "08", "bold": True},
    {"ozn": "A.2.", "n": "Změna stavu nepeněžních složek pracovního kapitálu", "r": "09", "bold": True},
    {"ozn": "A.2.1.", "n": "Změna stavu pohledávek (+/-)", "r": "10", "bold": False},
    {"ozn": "A.2.2.", "n": "Změna stavu krátkodobých závazků (+/-)", "r": "11", "bold": False},
    {"ozn": "A.2.3.", "n": "Změna stavu zásob (+/-)", "r": "12", "bold": False},
    {"ozn": "A.**", "n": "Čistý peněžní tok z provozní činnosti před zdaněním", "r": "13", "bold": True},
    {"ozn": "A.***", "n": "Čistý peněžní tok z provozní činnosti", "r": "14", "bold": True},
    {"ozn": "", "n": "PENĚŽNÍ TOKY Z INVESTIČNÍ ČINNOSTI", "r": "15", "bold": True},
    {"ozn": "B.1.", "n": "Výdaje spojené s nabytím stálých aktiv", "r": "16", "bold": False},
    {"ozn": "B.2.", "n": "Příjmy z prodeje stálých aktiv", "r": "17", "bold": False},
    {"ozn": "B.***", "n": "Čistý peněžní tok z investiční činnosti", "18": "B_CELKEM", "bold": True},
    {"ozn": "", "n": "PENĚŽNÍ TOKY Z FINANČNÍCH ČINNOSTÍ", "r": "19", "bold": True},
    {"ozn": "C.1.", "n": "Dopady změn dlouhodobých závazků", "r": "20", "bold": False},
    {"ozn": "C.2.1.", "n": "Zvýšení základního kapitálu (+)", "r": "21", "bold": False},
    {"ozn": "C.2.6.", "n": "Vyplacené dividendy (-)", "r": "22", "bold": False},
    {"ozn": "C.***", "n": "Čistý peněžní tok z finanční činnosti", "r": "CELKEM_FČ", "bold": True},
    {"ozn": "F.", "n": "Čisté zvýšení, resp. snížení peněžních prostředků", "r": "(+/-)", "bold": True},
    {"ozn": "R.", "n": "Stav peněžních prostředků na konci účetního období", "r": "CELKEM_KONEC", "bold": True},
]

class AccountingEngine:
    """Třída pro výpočet účetních dat a reportů."""

    def __init__(self, klient_id, execute_query_fn=None, metoda_zasob='B'):
        self.klient_id = klient_id

        # Pokud funkce není předána, zkusíme použít globální (pokud je importována)
        if execute_query_fn is None:
            from core.database import execute_query
            self._execute_query_fn = execute_query
        else:
            self._execute_query_fn = execute_query_fn

        # Spuštění údržby DB při startu
        self.zkontroluj_a_oprav_db()
        self.opravit_strukturu_rozvrhu()
        self.metoda_zasob = metoda_zasob

    def execute_query(self, sql, params=()):
        """Metoda, kterou volají všechny ostatní funkce v této třídě."""
        return self._execute_query_fn(sql, params)

    def get_dashboard_data(self, d_od, d_do):
        """Načte data pro dashboard – musí vracet přesně 8 sloupců."""
        sql = """
            SELECT 
                T.datum as datum,
                T.datum_splatnosti as datum_splatnosti,
                COALESCE(S.nazev, '-') as subjekt,
                COALESCE(S.email, '-') as email,
                COALESCE(S.ico, '-') as ico,
                CASE 
                    WHEN P.ucet LIKE '311%' THEN 'Pohledávka'
                    WHEN P.ucet LIKE '321%' THEN 'Závazek'
                END as typ,
                CAST(P.castka AS FLOAT) as castka,
                T.popis as popis
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            LEFT JOIN Subjekty S ON T.subjekt_id = S.id
            WHERE T.klient_id = ? 
            AND T.is_deleted = 0
            AND T.datum BETWEEN ? AND ?
            AND (P.ucet LIKE '311%' OR P.ucet LIKE '321%')
            ORDER BY T.datum DESC
        """
        try:
            # OPRAVA: Použití vnitřní metody instance místo přímého importu
            return self.execute_query(sql, (self.klient_id, d_od, d_do))
        except Exception as e:
            print(f"SQL Error: {e}")
            return []

    def zkontroluj_a_oprav_db(self):
        """
        Zkontroluje a doplní základní sloupce (is_deleted, subjekt_id atd.)
        a tabulky (AuditLog, Subjekty) v MS SQL Serveru.
        """
        try:
            with Database() as conn:
                cursor = conn.cursor()

                # 1. Kontrola sloupce 'datum_uzaverky' v tabulce Klienti
                res_uzaverka = execute_query("SELECT col_length('Klienti', 'datum_uzaverky')")
                if not res_uzaverka or res_uzaverka[0][0] is None:
                    cursor.execute("ALTER TABLE Klienti ADD datum_uzaverky DATE NULL;")

                # 2. Kontrola sloupce 'created_at' v tabulce Transakce
                res_created = execute_query("SELECT col_length('Transakce', 'created_at')")
                if not res_created or res_created[0][0] is None:
                    cursor.execute("ALTER TABLE Transakce ADD created_at DATETIME DEFAULT GETDATE();")

                # 3. Kontrola sloupce 'is_deleted' v tabulce Transakce (BIT pro MS SQL)
                res_deleted = execute_query("SELECT col_length('Transakce', 'is_deleted')")
                if not res_deleted or res_deleted[0][0] is None:
                    cursor.execute("ALTER TABLE Transakce ADD is_deleted BIT NOT NULL DEFAULT 0;")
                    cursor.execute("UPDATE Transakce SET is_deleted = 0 WHERE is_deleted IS NULL;")

                # 4. PRIDÁNO: Kontrola sloupce 'subjekt_id' v tabulce Transakce pro Dashboard
                res_sub_id = execute_query("SELECT col_length('Transakce', 'subjekt_id')")
                if not res_sub_id or res_sub_id[0][0] is None:
                    cursor.execute("ALTER TABLE Transakce ADD subjekt_id INT NULL;")

                # 5. Kontrola a vytvoření tabulky AuditLog
                audit_sql = """
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLog' AND xtype='U')
                    BEGIN
                        CREATE TABLE AuditLog (
                            id INT IDENTITY(1,1) PRIMARY KEY,
                            transakce_id INT,
                            datum_zmeny DATETIME DEFAULT GETDATE(),
                            typ_akce NVARCHAR(50), 
                            puvodni_data NVARCHAR(MAX), 
                            novy_data NVARCHAR(MAX) 
                        );
                    END
                """
                cursor.execute(audit_sql)

                # 6. PRIDÁNO: Kontrola a vytvoření tabulky Subjekty pro Dashboard
                subjekty_sql = """
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Subjekty' AND xtype='U')
                    BEGIN
                        CREATE TABLE Subjekty (
                            id INT IDENTITY(1,1) PRIMARY KEY,
                            klient_id INT NOT NULL,
                            nazev NVARCHAR(200) NOT NULL,
                            email NVARCHAR(150),
                            telefon NVARCHAR(50),
                            ico NVARCHAR(20)
                        );
                    END
                """
                cursor.execute(subjekty_sql)

                conn.commit()
                print("✅ Databáze byla úspěšně zkontrolována a aktualizována.")

        except Exception as e:
            print(f"❌ Chyba při automatické opravě DB: {e}")

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

    def upravit_transakci(self, transakce_id, nove_datum, nove_datum_splatnosti, novy_popis, novy_doklad,
                          ucet_md, ucet_dal, castka, sazba_dph, smer_dph_popis):
        """
        Komplexní úprava transakce:
        1. Kontrola uzávěrek pro staré i nové datum.
        2. Aktualizace hlavičky v SQL (včetně splatnosti).
        3. Kompletní přepis účetních pohybů.
        """
        # 1. Načtení starého stavu pro kontrolu uzávěrky
        stary_stav = self.get_transakce_detail(transakce_id)
        if not stary_stav:
            raise ValueError("Transakce neexistuje.")

        # Kontrola, zda nejsou období uzamčena
        self.zkontroluj_zda_je_otevreno(stary_stav['datum'])
        self.zkontroluj_zda_je_otevreno(nove_datum)

        try:
            # 2. Příprava výpočtů (Logika shodná se save_transakce)
            base = float(castka)
            tax = 0.0
            u_dph, s_dph, u_opp, s_opp = None, None, None, None

            if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:
                tax = base * (float(sazba_dph) / 100)
                sz = self.get_dph_sazby().get(float(sazba_dph))
                if smer_dph_popis == 'DPH na VSTUPU (MD)':
                    u_dph, s_dph, u_opp, s_opp = sz['vstup'], 'MD', ucet_dal, 'D'
                else:
                    u_dph, s_dph, u_opp, s_opp = sz['vystup'], 'D', ucet_md, 'MD'
            else:
                if str(ucet_md).startswith(('5', '0', '1', '2', '3')):
                    u_opp, s_opp = ucet_dal, 'D'
                else:
                    u_opp, s_opp = ucet_md, 'MD'

            total = base + tax

            with Database() as conn:
                cursor = conn.cursor()

                # 3. UPDATE HLAVIČKY (Důležité: nove_datum_splatnosti je zde jako druhý parametr)
                sql_upd = """
                    UPDATE Transakce 
                    SET datum = ?, datum_splatnosti = ?, popis = ?, doklad_cislo = ?
                    WHERE id = ? AND klient_id = ?
                """
                cursor.execute(sql_upd, (
                nove_datum, nove_datum_splatnosti, novy_popis, novy_doklad, transakce_id, self.klient_id))

                # 4. Smazání a znovuvytvoření pohybů
                cursor.execute("DELETE FROM UcetniPohyby WHERE transakce_id = ?", (transakce_id,))

                sql_pohyb = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?, ?, ?, ?, ?)"

                # Základ
                u_z = ucet_md if s_opp == 'D' else ucet_dal
                s_z = 'MD' if s_opp == 'D' else 'D'
                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, u_z, s_z, base))

                # DPH
                if tax > 0 and u_dph:
                    cursor.execute(sql_pohyb, (transakce_id, self.klient_id, u_dph, s_dph, tax))

                # Celkem
                cursor.execute(sql_pohyb, (transakce_id, self.klient_id, u_opp, s_opp, total))

                conn.commit()
                return True

        except Exception as e:
            print(f"Chyba při editaci transakce ID {transakce_id}: {e}")
            raise e

    def get_transakce_detail(self, transakce_id):
        """
        Načte kompletní detail transakce z databáze pro potřeby editace.
        Vrací slovník s hlavičkou (včetně splatnosti) a seznamem účetních pohybů.
        """
        sql = """
            SELECT T.datum, T.datum_splatnosti, T.doklad_cislo, T.popis, 
                   P.ucet, P.smer, P.castka
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.id = ? AND T.klient_id = ? AND T.is_deleted = 0
        """
        try:
            from core.database import execute_query
            results = execute_query(sql, (transakce_id, self.klient_id))

            if not results:
                return None

            # 1. Naplnění hlavičky transakce (data z prvního řádku výsledku)
            detail = {
                'id': transakce_id,
                'datum': results[0][0],
                'datum_splatnosti': results[0][1],  # Důležité pro editační pole
                'doklad': results[0][2],
                'popis': results[0][3],
                'pohyby': []
            }

            # 2. Načtení všech účetních pohybů (řádků MD/D)
            suma_objem = 0.0
            for row in results:
                detail['pohyby'].append({
                    'ucet': row[4],
                    'smer': row[5],
                    'castka': float(row[6])
                })
                # Výpočet celkového objemu dokladu (pro zobrazení v UI)
                if row[5] == 'MD':
                    suma_objem += float(row[6])

            detail['objem'] = suma_objem
            return detail

        except Exception as e:
            print(f"Chyba při načítání detailu transakce {transakce_id}: {e}")
            return None

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
        sql_query = """
        SELECT 
            SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) AS SumaMD,
            SUM(CASE WHEN P.smer = 'D' THEN P.castka ELSE 0 END) AS SumaD
        FROM UcetniPohyby P
        JOIN Transakce T ON T.id = P.transakce_id
        WHERE P.klient_id = ? AND P.ucet = ? AND T.is_deleted = 0
        """
        result = execute_query(sql_query, (self.klient_id, ucet))

        if result and result[0][0] is not None:
            suma_md = result[0][0]
            suma_d = result[0][1]
            zustatek = suma_md - suma_d
            return zustatek
        return 0.0

    def get_pohyby_uctu(self, ucet, datum_od=None, datum_do=None):
        sql = """
            SELECT T.datum, T.doklad_cislo, T.popis, P.smer, P.castka, P.ucet,
            (SELECT nazev FROM UctovyRozvrh WHERE cislo = P.ucet)
            FROM Transakce T JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.klient_id = ? AND P.ucet = ? AND T.is_deleted = 0
        """
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
        zustatky = defaultdict(float)
        sql = """
            SELECT 
                P.ucet,
                SUM(CASE WHEN P.smer = 'MD' THEN P.castka ELSE 0 END) AS SumaMD,
                SUM(CASE WHEN P.smer = 'D' THEN P.castka ELSE 0 END) AS SumaD
            FROM UcetniPohyby P
            JOIN Transakce T ON T.id = P.transakce_id
            WHERE P.klient_id = ? AND T.is_deleted = 0
            """
        params = [self.klient_id]

        if datum_od:
            sql += " AND T.datum >= ?"
            params.append(datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od)
        if datum_do:
            sql += " AND T.datum <= ?"
            params.append(datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do)

        sql += " GROUP BY P.ucet"

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                raw_zustatky = cursor.fetchall()

            def safe_float(val):
                return float(val) if val is not None else 0.0

            for row in raw_zustatky:
                ucet = row[0]
                suma_md = safe_float(row[1])
                suma_d = safe_float(row[2])
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
        dph_sazby = self.get_dph_sazby()
        prehled = defaultdict(lambda: {'vstup': Decimal('0.0'), 'vystup': Decimal('0.0'), 'rozdil': Decimal('0.0')})
        celkem_rozdil = Decimal('0.0')

        vsechny_dph_ucty = []
        for sazba_dict in dph_sazby.values():
            if sazba_dict['vstup']: vsechny_dph_ucty.append(sazba_dict['vstup'].strip())
            if sazba_dict['vystup']: vsechny_dph_ucty.append(sazba_dict['vystup'].strip())

        vsechny_dph_ucty = list(set(filter(None, vsechny_dph_ucty)))
        if not vsechny_dph_ucty: return {'CELKEM': Decimal('0.0')}

        ucet_patterns = [f"{u}%" for u in vsechny_dph_ucty]
        placeholders = " OR ".join(["P.ucet LIKE ?" for _ in ucet_patterns])

        sql = f"""
            SELECT P.ucet, P.smer, P.castka, T.datum, T.id
            FROM UcetniPohyby P
            JOIN Transakce T ON T.id = P.transakce_id
            WHERE P.klient_id = ? AND T.is_deleted = 0
            AND ({placeholders})
            """
        params = [self.klient_id] + ucet_patterns

        if datum_od:
            sql += " AND T.datum >= ?"
            params.append(datum_od.strftime('%Y-%m-%d') if hasattr(datum_od, 'strftime') else datum_od)
        if datum_do:
            sql += " AND T.datum <= ?"
            params.append(datum_do.strftime('%Y-%m-%d') if hasattr(datum_do, 'strftime') else datum_do)

        try:
            with Database() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                pohyby = cursor.fetchall()

            for row in pohyby:
                ucet = row[0].strip()
                smer = row[1].strip().upper()
                castka_dec = Decimal(str(row[2] if row[2] is not None else 0.0))

                for sazba, ucty in dph_sazby.items():
                    vstup_cfg = ucty['vstup'].strip() if ucty['vstup'] else None
                    vystup_cfg = ucty['vystup'].strip() if ucty['vystup'] else None

                    if vstup_cfg and ucet.startswith(vstup_cfg) and smer == 'MD':
                        prehled[sazba]['vstup'] += castka_dec
                        break
                    elif vystup_cfg and ucet.startswith(vystup_cfg) and smer == 'D':
                        prehled[sazba]['vystup'] += castka_dec
                        break

            for sazba, data in prehled.items():
                rozdil = data['vystup'] - data['vstup']
                data['rozdil'] = rozdil
                celkem_rozdil += rozdil

            prehled['CELKEM'] = celkem_rozdil
            return dict(prehled)
        except Exception as e:
            print(f"CHYBA DPH: {e}")
            return {'CELKEM': Decimal('0.0')}

    def get_report_data(self, datum_od=None, datum_do=None, detailni=True):
        sql = """
            SELECT P.ucet, R.nazev, R.typ_uctu, SUM(P.castka), P.smer
            FROM UcetniPohyby P 
            LEFT JOIN UctovyRozvrh R ON P.ucet = R.cislo
            JOIN Transakce T ON P.transakce_id = T.id
            WHERE T.klient_id = ? AND T.is_deleted = 0
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
                temp[u]['nazev'] = r[1] if r[1] else u_raw
                if smer == 'MD': temp[u]['bal'] += val
                else: temp[u]['bal'] -= val

            for u, data in temp.items():
                b, t, n = data['bal'], data['typ'], data['nazev']
                if abs(b) < 0.005: continue
                item = {'ucet': u, 'nazev': n, 'castka': abs(b)}
                if t == 'A':
                    rep['aktiva'].append(item); rep['suma_aktiva'] += b
                elif t in ['P', 'P*', 'Z']:
                    rep['pasiva'].append(item); rep['suma_pasiva'] += abs(b)
                elif t == 'N':
                    rep['naklady'].append(item); rep['suma_naklady'] += abs(b)
                elif t == 'V':
                    rep['vynosy'].append(item); rep['suma_vynosy'] += abs(b)

            hv = rep['suma_vynosy'] - rep['suma_naklady']
            rep['hospodarsky_vysledek'] = hv
            rep['pasiva'].append({'ucet': 'HV', 'nazev': 'Hospodářský výsledek', 'castka': hv})
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
    def save_transakce(self, datum, datum_splatnosti, popis, doklad_cislo, ucet_md_zaklad, ucet_dal_zaklad, castka_bez_dph, sazba_dph,
                       smer_dph_popis):
        """Uloží transakci do DB včetně data splatnosti."""
        try:
            self.zkontroluj_zda_je_otevreno(datum)
            self.validuj_ceske_standardy(ucet_md_zaklad, ucet_dal_zaklad)

            base = float(castka_bez_dph)
            tax = 0.0
            u_dph, s_dph, u_opp, s_opp = None, None, None, None

            if smer_dph_popis != 'Neučtovat' and float(sazba_dph) > 0.0:
                tax = base * (float(sazba_dph) / 100)
                sz = self.get_dph_sazby().get(float(sazba_dph))
                if smer_dph_popis == 'DPH na VSTUPU (MD)':
                    u_dph, s_dph, u_opp, s_opp = sz['vstup'], 'MD', ucet_dal_zaklad, 'D'
                else:
                    u_dph, s_dph, u_opp, s_opp = sz['vystup'], 'D', ucet_md_zaklad, 'MD'
            else:
                if str(ucet_md_zaklad).startswith(('5', '0', '1', '2', '3')):
                    u_opp, s_opp = ucet_dal_zaklad, 'D'
                else:
                    u_opp, s_opp = ucet_md_zaklad, 'MD'

            total = base + tax

            with Database() as conn:
                cur = conn.cursor()
                # SQL INSERT s novým sloupcem datum_splatnosti
                sql_hlavicka = """
                    SET NOCOUNT ON;
                    INSERT INTO Transakce (klient_id, datum, datum_splatnosti, popis, doklad_cislo, is_deleted) 
                    VALUES (?, ?, ?, ?, ?, 0);
                    SELECT SCOPE_IDENTITY();
                """
                cur.execute(sql_hlavicka, (self.klient_id, datum, datum_splatnosti, popis, doklad_cislo))
                tid = int(cur.fetchone()[0])

                sql_ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?,?,?,?,?)"
                u_z = ucet_md_zaklad if s_opp == 'D' else ucet_dal_zaklad
                s_z = 'MD' if s_opp == 'D' else 'D'
                cur.execute(sql_ins, (tid, self.klient_id, u_z, s_z, base))
                if tax > 0 and u_dph:
                    cur.execute(sql_ins, (tid, self.klient_id, u_dph, s_dph, tax))
                cur.execute(sql_ins, (tid, self.klient_id, u_opp, s_opp, total))
                conn.commit()
                return tid
        except Exception as e:
            print(f"Save error: {e}")
            raise e


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
        """Uzavře 5xx/6xx -> 710 a Rozvahu -> 702 s ošetřením NameError."""
        datum_uzaverky = date(rok, 12, 31)
        datum_od = date(rok, 1, 1)

        # Inicializace proměnných, aby vždy existovaly
        rows_710 = []
        rows_702 = []

        try:
            # 1. Kontrola existující uzávěrky
            check = execute_query(
                "SELECT id, is_deleted FROM Transakce WHERE doklad_cislo = ? AND klient_id = ?",
                (f"UZAV-{rok}", self.klient_id)
            )

            if check:
                is_del = check[0][1]
                if is_del:
                    return f"⚠️ Uzávěrka pro rok {rok} již existuje v KOŠI. Musíte ji v Historii trvale smazat, než ji spustíte znovu."
                else:
                    return f"⚠️ Uzávěrka pro rok {rok} již existuje jako aktivní transakce."

            # 2. Načtení zůstatků pro 710 (Výsledovka - náklady a výnosy)
            sql_710 = """
                SELECT P.ucet, SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)
                FROM UcetniPohyby P JOIN Transakce T ON P.transakce_id = T.id
                WHERE T.klient_id = ? AND T.datum >= ? AND T.datum <= ? AND T.is_deleted = 0
                AND (P.ucet LIKE '5%' OR P.ucet LIKE '6%')
                GROUP BY P.ucet 
                HAVING ABS(SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)) > 0.005
            """
            rows_710 = execute_query(sql_710, (self.klient_id, datum_od, datum_uzaverky)) or []

            # 3. Načtení zůstatků pro 702 (Rozvaha - majetek a závazky)
            sql_702 = """
                SELECT P.ucet, SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)
                FROM UcetniPohyby P JOIN Transakce T ON P.transakce_id = T.id
                WHERE T.klient_id = ? AND T.datum <= ? AND T.is_deleted = 0
                AND (P.ucet LIKE '[0-49]%')
                GROUP BY P.ucet 
                HAVING ABS(SUM(CASE WHEN P.smer='MD' THEN P.castka ELSE -P.castka END)) > 0.005
            """
            rows_702 = execute_query(sql_702, (self.klient_id, datum_uzaverky)) or []

            # 4. Kontrola, zda je co zavírat
            if not rows_710 and not rows_702:
                return "⚠️ Žádná data k uzavření (všechny účty mají nulový zůstatek nebo neexistují transakce)."

            # 5. Samotný proces zápisu do databáze
            self.zajisti_existenci_uctu("710", "Účet zisků a ztrát")
            self.zajisti_existenci_uctu("702", "Konečný účet rozvažný")

            with Database() as conn:
                cursor = conn.cursor()

                # OPRAVA PRO MS SQL SERVER:
                # 1. SET NOCOUNT ON vypne zprávy typu "1 row affected", které pletou Python
                # 2. OUTPUT INSERTED.id je nejspolehlivější cesta k získání nového ID
                sql_hlavicka = """
                    SET NOCOUNT ON;
                    INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo, created_at, is_deleted)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, GETDATE(), 0);
                """

                cursor.execute(sql_hlavicka, (self.klient_id, datum_uzaverky, f"Uzávěrka roku {rok}", f"UZAV-{rok}"))

                # Načtení ID nově vytvořené uzávěrky
                res_id = cursor.fetchone()
                if not res_id:
                    return "❌ Databáze nevrátila ID nové transakce."

                transakce_id = int(res_id[0])

                sql_ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?, ?, ?, ?, ?)"
                hv = 0.0

                # Zápis pohybů pro 710 (převod výsledovky)
                for r in rows_710:
                    ucet, bilance = r[0], float(r[1])
                    if bilance > 0:  # Náklad (MD) -> musíme dát na D
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'D', abs(bilance)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'MD', abs(bilance)))
                        hv -= abs(bilance)
                    else:  # Výnos (D) -> musíme dát na MD
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'MD', abs(bilance)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'D', abs(bilance)))
                        hv += abs(bilance)

                # Zápis pohybů pro 702 (převod rozvahy)
                for r in rows_702:
                    ucet, bilance = r[0], float(r[1])
                    if bilance > 0:  # Aktivum (MD) -> na D
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'D', abs(bilance)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'MD', abs(bilance)))
                    else:  # Pasivum (D) -> na MD
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, ucet, 'MD', abs(bilance)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'D', abs(bilance)))

                # Převod konečného HV (710 -> 702)
                if abs(hv) > 0.005:
                    if hv > 0:  # Zisk
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'MD', abs(hv)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'D', abs(hv)))
                    else:  # Ztráta
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '710', 'D', abs(hv)))
                        cursor.execute(sql_ins, (transakce_id, self.klient_id, '702', 'MD', abs(hv)))

                conn.commit()
                return f"✅ Rok {rok} úspěšně uzavřen! Doklad UZAV-{rok}."

        except Exception as e:
            return f"❌ Chyba při uzávěrce: {str(e)}"

    def otevrit_novy_rok(self, rok_k_otevreni):
        """
        Otevře nový rok (701) na základě uzávěrky (702) z minulého roku.
        Parametrem je rok, který chceme ZAČÍT účtovat (např. 2026).
        """
        stary_rok = rok_k_otevreni - 1
        datum_otevreni = date(rok_k_otevreni, 1, 1)
        doklad_uzav = f"UZAV-{stary_rok}"
        doklad_poc = f"POC-{rok_k_otevreni}"

        # 1. Kontrola, zda už počáteční stav neexistuje
        check_exists = execute_query(
            "SELECT id FROM Transakce WHERE doklad_cislo = ? AND klient_id = ? AND is_deleted = 0",
            (doklad_poc, self.klient_id)
        )
        if check_exists:
            return f"⚠️ Počáteční stavy pro rok {rok_k_otevreni} již byly vygenerovány ({doklad_poc})."

        # 2. Najdeme data z uzávěrky minulého roku (vše kromě závěrkových účtů)
        sql = """
            SELECT P.ucet, P.smer, P.castka 
            FROM UcetniPohyby P 
            JOIN Transakce T ON T.id = P.transakce_id 
            WHERE T.doklad_cislo = ? AND P.klient_id = ? AND T.is_deleted = 0
            AND P.ucet NOT IN ('702','710')
        """
        rows = execute_query(sql, (doklad_uzav, self.klient_id))

        # 3. Najdeme HV z minulého roku na účtu 702
        sqlhv = """
            SELECT SUM(CASE WHEN P.smer='D' THEN P.castka ELSE -P.castka END) 
            FROM UcetniPohyby P 
            JOIN Transakce T ON T.id = P.transakce_id 
            WHERE T.doklad_cislo = ? AND P.klient_id = ? AND P.ucet = '702' AND T.is_deleted = 0
        """
        reshv = execute_query(sqlhv, (doklad_uzav, self.klient_id))
        hv = reshv[0][0] if reshv and reshv[0][0] is not None else 0.0

        if not rows and abs(hv) < 0.01:
            return f"⚠️ Nenalezena platná uzávěrka pro rok {stary_rok} (doklad {doklad_uzav})."

        self.zajisti_existenci_uctu("701", "Počáteční účet rozvažný")
        self.zajisti_existenci_uctu("431", "Výsledek hospodaření ve schvalovacím řízení")

        try:
            with Database() as conn:
                cur = conn.cursor()
                # Vytvoření hlavičky počátečního stavu
                sql_head = """
                    SET NOCOUNT ON;
                    INSERT INTO Transakce (klient_id, datum, popis, doklad_cislo, created_at, is_deleted)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, GETDATE(), 0)
                """
                cur.execute(sql_head, (self.klient_id, datum_otevreni, f"Počáteční stavy {rok_k_otevreni}", doklad_poc))

                res_id = cur.fetchone()
                if not res_id:
                    return "❌ Nepodařilo se vytvořit transakci pro nový rok."
                tid = int(res_id[0])

                ins = "INSERT INTO UcetniPohyby (transakce_id, klient_id, ucet, smer, castka) VALUES (?,?,?,?,?)"

                # Přenos rozvahových zůstatků
                for r in rows:
                    u, s_stary, val = r[0], r[1], float(r[2])
                    # Obracíme strany: Co bylo na D (uzavření), jde na MD (otevření)
                    if s_stary == 'D':
                        cur.execute(ins, (tid, self.klient_id, u, 'MD', val))
                        cur.execute(ins, (tid, self.klient_id, '701', 'D', val))
                    else:
                        cur.execute(ins, (tid, self.klient_id, u, 'D', val))
                        cur.execute(ins, (tid, self.klient_id, '701', 'MD', val))

                # Otevření HV (zisk byl na 702 D, ztráta na 702 MD)
                if abs(hv) > 0.005:
                    val_hv = abs(float(hv))
                    if hv > 0:  # Zisk minulého roku -> 431 D
                        cur.execute(ins, (tid, self.klient_id, '431', 'D', val_hv))
                        cur.execute(ins, (tid, self.klient_id, '701', 'MD', val_hv))
                    else:  # Ztráta minulého roku -> 431 MD
                        cur.execute(ins, (tid, self.klient_id, '431', 'MD', val_hv))
                        cur.execute(ins, (tid, self.klient_id, '701', 'D', val_hv))

                conn.commit()
                return f"✅ Rok {rok_k_otevreni} úspěšně otevřen! (Doklad {doklad_poc})."
        except Exception as e:
            return f"❌ Chyba při otevírání roku: {str(e)}"

    def get_zakladni_ucty_podle_tridy(self, trida_prefix):
        """Vrátí pouze trojciferné základní účty (např. 501, 511)."""
        # Používáme LEN(cislo) = 3, aby se odfiltrovala analytika (501.001 atd.)
        sql = "SELECT cislo, nazev FROM UctovyRozvrh WHERE cislo LIKE ? AND LEN(cislo) = 3 ORDER BY cislo"
        try:
            results = execute_query(sql, (f"{trida_prefix}%",))
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání základních účtů: {e}")
            return []

    def get_analytika_pro_ucet(self, zaklad_cislo):
        """Vrátí podúčty pro daný základ (např. pro 501 najde 501.001)."""
        # Hledáme účty, které začínají "501." a mají více než 3 znaky
        sql = "SELECT cislo, nazev FROM UctovyRozvrh WHERE cislo LIKE ? AND LEN(cislo) > 3 ORDER BY cislo"
        try:
            results = execute_query(sql, (f"{zaklad_cislo}.%",))
            return [f"{row[0]} - {row[1]}" for row in results]
        except Exception as e:
            print(f"Chyba při načítání analytiky: {e}")
            return []

    def get_working_capital_metrics(self, datum_k):
        """Vypočítá složky pracovního kapitálu k určitému datu."""
        zustatky = self.spocti_zustatky(datum_do=datum_k)

        # Gross WC: Třídy 1, 2 a účet 311
        gross_wc = sum(v for u, v in zustatky.items() if u.startswith(('1', '2', '311')))

        # Krátkodobé závazky: Účty 321, 33x, 34x (pokud jsou v pasivech)
        current_liabilities = abs(sum(v for u, v in zustatky.items() if u.startswith(('321', '33', '34')) and v < 0))

        return {
            "gross_wc": gross_wc,
            "net_wc": gross_wc - current_liabilities,
            "liquid_wc": sum(v for u, v in zustatky.items() if u.startswith('2'))
        }

    def get_income_expense_trend(self, d_od, d_do):
        """
        Vrátí měsíční sumy příjmů (třída 6) a výdajů (třída 5).
        """
        # SQL dotaz upravený pro MS SQL Server
        sql = """
            SELECT 
                FORMAT(T.datum, 'yyyy-MM') as mesic,
                CAST(SUM(CASE WHEN P.ucet LIKE '6%' THEN P.castka ELSE 0 END) AS FLOAT) as prijmy,
                CAST(SUM(CASE WHEN P.ucet LIKE '5%' THEN P.castka ELSE 0 END) AS FLOAT) as vydaje
            FROM Transakce T
            JOIN UcetniPohyby P ON T.id = P.transakce_id
            WHERE T.is_deleted = 0 
              AND T.klient_id = ? 
              AND T.datum BETWEEN ? AND ?
            GROUP BY FORMAT(T.datum, 'yyyy-MM')
            ORDER BY mesic ASC
        """
        try:
            results = execute_query(sql, (self.klient_id, d_od, d_do))

            # Zajištění, že vracíme list tuplů (nebo prázdný list),
            # aby Pandas mohl správně mapovat 3 sloupce.
            if not results:
                return []

            # Převedeme výsledek na seznam tuplů, pokud by vracel něco jiného
            return [tuple(row) for row in results]

        except Exception as e:
            print(f"Chyba při načítání trendu: {e}")
            return []

    def get_vykaz_podklady(self, klient_id, datum_k, typ_vykazu):
        self.klient_id = klient_id
        # Načtení zůstatků k aktuálnímu dni
        zustatky = self.spocti_zustatky(datum_do=datum_k)
        # Načtení počátečních stavů (k 1.1. daného roku)
        datum_start_roku = date(datum_k.year, 1, 1)
        zustatky_start = self.spocti_zustatky(datum_do=datum_start_roku)

        report_data = []

        # Výběr šablony
        if "Aktiva" in typ_vykazu:
            sablona, mapovani = SABLONA_AKTIVA_FULL, MAPOVANI_AKTIV_FULL
        elif "Pasiva" in typ_vykazu:
            sablona, mapovani = SABLONA_PASIVA_FULL, MAPOVANI_PASIVA_FULL
        elif "Vysledovka" in typ_vykazu:
            sablona, mapovani = SABLONA_VYSLEDOVKA_FULL, MAPOVANI_VYSLEDOVKY_FULL
        else:
            sablona, mapovani = SABLONA_CF_FULL, MAPOVANI_CF_FULL

        vals = {}
        for radek in sablona:
            r_id = radek["r"]
            masky = mapovani.get(r_id, [])

            # Logika výpočtu pro CF
            if r_id == "P0":  # Počáteční peníze
                val = sum(float(v) for u, v in zustatky_start.items() if any(str(u).startswith(m) for m in masky))
            elif r_id == "R":  # Koncové peníze
                val = sum(float(v) for u, v in zustatky.items() if any(str(u).startswith(m) for m in masky))
            elif r_id == "A1":  # Zisk (třeba dotáhnout z výsledovky)
                res_v = self.get_report_data(datum_od=datum_start_roku, datum_do=datum_k)
                val = res_v['hospodarsky_vysledek'] if res_v else 0.0
            elif r_id == "F":  # Čistá změna
                val = vals.get("R", 0) - vals.get("P0", 0)
            elif r_id == "A_CELKEM":
                val = vals.get("A1", 0) + vals.get("A21", 0) + vals.get("A22", 0)
            else:
                # Ostatní řádky přes sčítání analytiky
                val = sum(float(v) for u, v in zustatky.items() if any(str(u).startswith(m) for m in masky))
                if r_id.startswith('A'): val = abs(val)  # Odpisy apod. kladně
                if r_id in ['B', 'C']: val = -abs(val)  # Investice a splátky záporně

            vals[r_id] = val
            minule = self.get_minule_obdobi_netto(typ_vykazu, datum_k.year, r_id)

            # Vizuální trik: U nadpisů skryjeme čísla pro design přes celou tabulku
            if radek["bold"] and r_id not in ["P0", "R", "F", "A_CELKEM"]:
                val_b, val_n, val_m = None, None, None
            else:
                val_b, val_n, val_m = val, val, minule

            report_data.append({
                "Označení": radek["ozn"],
                "POLOŽKA": radek["n"],
                "Číslo řádku": r_id,
                "Brutto": val_b,
                "Netto": val_n,
                "Minulé období": val_m,
                "is_bold": radek["bold"]
            })
        return report_data

    def get_minule_obdobi_netto(self, typ, rok, r_kod):
        """Vyhledá v archivu konkrétního klienta hodnotu z loňského roku."""
        sql = """
            SELECT castka_bezne FROM VykazyPolozky P 
            JOIN VykazyArchiv A ON P.vykaz_id = A.id 
            WHERE A.klient_id = ? AND A.typ_vykazu = ? AND A.rok = ? AND P.kod_polozky = ?
        """
        res = self.execute_query(sql, (self.klient_id, typ, rok - 1, r_kod))
        return float(res[0][0]) if res else 0.0

    def render_professional_assets_table(engine, datum_k):
        st.markdown("### ⚖️ Rozvaha: AKTIVA (Plný rozsah)")

        # Načtení dat přes novou agregační logiku
        rows = engine.get_rozvaha_assets_full(datum_k)
        df = pd.DataFrame(rows)

        # Definice sloupců přesně podle úředního tiskopisu
        cols_rename = {
            "ozn": "Označení (a)",
            "polozka": "AKTIVA (b)",
            "radek": "Číslo řádku (c)",
            "brutto": "Brutto (1)",
            "korekce": "Korekce (2)",
            "netto": "Netto (3)",
            "minule": "Minulé úč. období (4)",
            "zdroj": "Zdroj (Analytika)"
        }

        df_display = df.rename(columns=cols_rename)

        # Funkce pro zvýraznění sekcí (Bold + Dark Background)
        def style_rows(row):
            is_bold = df.iloc[row.name]["is_bold"]
            if is_bold:
                return ['font-weight: bold; background-color: #1a1c23; color: #ffffff' for _ in row]
            return ['' for _ in row]

        st.data_editor(
            df_display.style.apply(style_rows, axis=1),
            column_config={
                "is_bold": None,  # Skrytí pomocného sloupce
                "Brutto (1)": st.column_config.NumberColumn(format="%.2f"),
                "Korekce (2)": st.column_config.NumberColumn(format="%.2f"),
                "Netto (3)": st.column_config.NumberColumn(format="%.2f"),
                "Zdroj (Analytika)": st.column_config.TextColumn(help="Syntetické účty tvořící tento řádek")
            },
            disabled=["Označení (a)", "Číslo řádku (c)"],  # Předepsané hodnoty nelze měnit
            hide_index=True,
            use_container_width=True,
            key="full_assets_editor_pro"
        )

    def zobrazit_profesionalni_rozvahu_ui(engine, datum_k):
        st.subheader("⚖️ Rozvaha: AKTIVA (Plný rozsah)")

        # Načtení dat pro aktuálního klienta
        data = engine.get_vykaz_podklady(engine.klient_id, datum_k, "Rozvaha_Aktiva")
        df = pd.DataFrame(data)

        # Styl: Bold pro hlavní sekce (např. AKTIVA CELKEM)
        def style_vykaz(row):
            return ['font-weight: bold; background-color: #1a1c23' if row['is_bold'] else '' for _ in row]

        st.data_editor(
            df.style.apply(style_vykaz, axis=1),
            column_config={
                "is_bold": None,  # Skrytý sloupec
                "Brutto (1)": st.column_config.NumberColumn(format="%.2f"),
                "Korekce (2)": st.column_config.NumberColumn(format="%.2f"),
                "Netto (3)": st.column_config.NumberColumn(format="%.2f"),
                "Minulé úč. období (4)": st.column_config.NumberColumn(format="%.2f"),
                "Zdroj (Účty)": st.column_config.TextColumn("Zdroj", help="Syntetické účty tvořící sumu")
            },
            disabled=["Označení (a)", "Číslo řádku (c)", "AKTIVA (b)"],  # Předepsaná pole jsou zamčená
            hide_index=True,
            use_container_width=True,
            key="full_balance_editor"
        )

    def ulozit_vykaz_do_archivu(self, typ_vykazu, rok, kvartal, df_polozky, metadata):
        """Uloží vygenerovaný výkaz do archivu (hlavička + položky)."""
        sql_header = """
            INSERT INTO VykazyArchiv (klient_id, typ_vykazu, rok, kvartal, sestaveno_k, nazev_jednotky, ico_jednotky)
            OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        # Bezpečné získání metadat s výchozími hodnotami
        h_params = (
            self.klient_id,
            typ_vykazu,
            rok,
            kvartal,
            metadata.get('sestaveno_k', date.today()),
            metadata.get('nazev_jednotky', 'Neznámá jednotka'),
            metadata.get('ico_jednotky', '0')
        )

        res = self.execute_query(sql_header, h_params)

        if not res:
            return False

        vykaz_id = res[0][0]

        # 2. Uložení položek výkazu
        sql_item = """
            INSERT INTO VykazyPolozky (vykaz_id, kod_polozky, nazev_polozky, zkratka_en, castka_bezne, is_vylouceno) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        for _, row in df_polozky.iterrows():
            self.execute_query(sql_item, (
                vykaz_id,
                str(row.get('Kód', '')),
                str(row.get('Položka', '')),
                str(row.get('Zkratka', '-')),
                float(row.get('Běžné', 0)),
                1 if row.get('Vyloučit') else 0
            ))
        return True

    def get_klient_info(self, klient_id):
        """Načte název a IČO firmy pro hlavičky výkazů."""
        sql = "SELECT nazev_firmy, ico FROM Klienti WHERE id = ?"
        try:
            res = self.execute_query(sql, (klient_id,))
            if res and len(res) > 0:
                return {"nazev": res[0][0], "ico": res[0][1]}
        except Exception as e:
            print(f"Chyba get_klient_info: {e}")

        return {"nazev": "Neznámá firma", "ico": "0"}

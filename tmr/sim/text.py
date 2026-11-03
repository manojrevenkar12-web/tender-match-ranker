"""German lot texts as buyers write them. Simulator only: the platform learns trades from these texts and
the labels buyers give them, and is tested on a blind set written by someone who never saw this file."""

from __future__ import annotations

import random

# Per trade: title words, work items (with {n} for a quantity) and optional norms / cost groups.
VOCAB: dict[str, dict[str, list[str]]] = {
    "erdarbeiten": {
        "title": ["Erdarbeiten", "Erd- und Gründungsarbeiten", "Baugrube", "Erdbau", "Aushub und Verfüllung"],
        "items": [
            "Oberboden abtragen und seitlich lagern, ca. {n} m²",
            "Baugrubenaushub Bodenklasse 3-5, {n} m³, inkl. Abtransport",
            "Boden lösen, laden und entsorgen (Z1.1), {n} m³",
            "Verfüllen der Arbeitsräume lagenweise verdichtet, {n} m³",
            "Planum herstellen, Ev2 ≥ 45 MN/m², {n} m²",
            "Bodenaustausch mit Schotter 0/45, {n} m³",
            "Wasserhaltung offen, Pumpensumpf, Vorhaltung {n} Wochen",
            "Grabenaushub für Grundleitungen, Tiefe bis 1,75 m, {n} m",
        ],
        "norms": ["DIN 18300", "DIN 18300 Erdarbeiten", "KG 310", "Homogenbereich B1"],
    },
    "rohbau": {
        "title": [
            "Rohbauarbeiten",
            "Beton- und Stahlbetonarbeiten",
            "Rohbau",
            "Mauer- und Betonarbeiten",
            "Stahlbetonbau",
        ],
        "items": [
            "Ortbeton C30/37 für Bodenplatte, d = 30 cm, {n} m³",
            "Betonstahl B500B liefern, schneiden, biegen und verlegen, {n} t",
            "Schalung für Wände, glatt, {n} m²",
            "Mauerwerk KS 17,5 cm, Mörtelgruppe IIa, {n} m²",
            "Stahlbetondecke als Halbfertigteil, {n} m²",
            "WU-Beton Wände Kellergeschoss, {n} m³",
            "Stützen C35/45, Sichtbeton SB2, {n} Stk",
            "Hochlochziegel 36,5 cm, Planziegel, {n} m²",
        ],
        "norms": ["DIN 18331", "DIN 18330", "KG 330", "KG 350", "DIN EN 206"],
    },
    "stahlbau": {
        "title": ["Stahlbauarbeiten", "Stahlbau", "Stahlkonstruktion", "Stahl- und Metallkonstruktion"],
        "items": [
            "Stahlkonstruktion S355 für Hallentragwerk liefern und montieren, {n} t",
            "HEA- und IPE-Profile, feuerverzinkt, {n} t",
            "Trapezblech als Dachtragschale, {n} m²",
            "Brandschutzbeschichtung R30 auf Stahlbauteilen, {n} m²",
            "Anschlussbleche, Kopfplatten, Ankerplatten, {n} kg",
            "Kranbahnträger inkl. Schienen, {n} m",
        ],
        "norms": ["DIN 18335", "DIN EN 1090 EXC2", "KG 330", "KG 360"],
    },
    "zimmerer": {
        "title": ["Zimmererarbeiten", "Zimmer- und Holzbauarbeiten", "Holzbau", "Dachstuhl"],
        "items": [
            "Dachstuhl aus KVH NSi C24 abbinden und aufstellen, {n} m³",
            "Brettschichtholz GL24h Pfetten, {n} m³",
            "Holzrahmenbauwände vorgefertigt, {n} m²",
            "Aufsparrendämmung Holzfaser 160 mm, {n} m²",
            "Dachschalung 24 mm, {n} m²",
            "Holzbalkendecke mit Schüttung, {n} m²",
        ],
        "norms": ["DIN 18334", "KG 360", "KG 330"],
    },
    "dachdecker": {
        "title": ["Dachdeckerarbeiten", "Dachabdichtung", "Dachdeckungsarbeiten", "Flachdach", "Steildach"],
        "items": [
            "Flachdachabdichtung zweilagig Bitumen, {n} m²",
            "Gefälledämmung EPS, im Mittel 200 mm, {n} m²",
            "Dachziegel Biberschwanz, Doppeldeckung, {n} m²",
            "Kunststoffbahn FPO 1,8 mm, mechanisch befestigt, {n} m²",
            "Extensive Dachbegrünung inkl. Drainschicht, {n} m²",
            "Lattung und Konterlattung, Unterdeckbahn, {n} m²",
            "Attikaabdeckung mit Bahnenanschluss, {n} m",
        ],
        "norms": ["DIN 18338", "DIN 18336", "Flachdachrichtlinie", "KG 360"],
    },
    "klempner": {
        "title": ["Klempnerarbeiten", "Spenglerarbeiten", "Bauklempnerei", "Dachentwässerung"],
        "items": [
            "Dachrinne halbrund Titanzink, NG 333, {n} m",
            "Fallrohr Titanzink DN 100, {n} m",
            "Ortgangverblechung Aluminium, {n} m",
            "Kehlblech Kupfer, {n} m",
            "Stehfalzdeckung Titanzink, {n} m²",
            "Notüberläufe und Speier, {n} Stk",
        ],
        "norms": ["DIN 18339", "KG 360"],
    },
    "fenster": {
        "title": [
            "Fensterarbeiten",
            "Metallbau",
            "Fenster und Außentüren",
            "Pfosten-Riegel-Fassade",
            "Metallbauarbeiten",
        ],
        "items": [
            "Kunststofffenster 3-fach verglast, Uw ≤ 0,9, {n} Stk",
            "Aluminium-Pfosten-Riegel-Fassade, {n} m²",
            "Hauseingangstür Aluminium mit Seitenteil, {n} Stk",
            "Fensterbänke außen Aluminium, {n} m",
            "Holz-Alu-Fenster, RC2, {n} Stk",
            "Geländer Stahl verzinkt mit Füllstäben, {n} m",
            "Rauch- und Wärmeabzug in der Fassade, {n} Stk",
        ],
        "norms": ["DIN 18360", "DIN 18355", "KG 334", "KG 337"],
    },
    "trockenbau": {
        "title": ["Trockenbauarbeiten", "Trockenbau", "Innenausbau Trockenbau", "Gipskartonarbeiten"],
        "items": [
            "Metallständerwand CW 75, doppelt beplankt GKB, {n} m²",
            "Abgehängte Decke GK, Q2, {n} m²",
            "Brandschutzwand F90, {n} m²",
            "Vorsatzschale freistehend, {n} m²",
            "Akustikdecke Mineralfaser 625x625, {n} m²",
            "Revisionsöffnungen in GK-Decken, {n} Stk",
            "Schachtwände F90, {n} m²",
        ],
        "norms": ["DIN 18340", "KG 342", "KG 353"],
    },
    "putz": {
        "title": ["Putzarbeiten", "Putz- und Stuckarbeiten", "Innenputz", "WDVS", "Fassadenputz"],
        "items": [
            "Kalkgipsputz einlagig, Q2, {n} m²",
            "Wärmedämmverbundsystem EPS 160 mm, {n} m²",
            "Mineralischer Oberputz, Körnung 2 mm, {n} m²",
            "Eckschutzschienen und Putzprofile, {n} m",
            "Sockelputz mit Abdichtung, {n} m²",
            "Mineralwolle-WDVS mit Brandriegeln, {n} m²",
        ],
        "norms": ["DIN 18350", "DIN 18345", "KG 335", "KG 345"],
    },
    "estrich": {
        "title": ["Estricharbeiten", "Estrich", "Estrich- und Dämmarbeiten"],
        "items": [
            "Zementestrich CT-C25-F4 schwimmend, 65 mm, {n} m²",
            "Calciumsulfatfließestrich auf Fußbodenheizung, {n} m²",
            "Trittschalldämmung EPS-T 30-2, {n} m²",
            "Randdämmstreifen, {n} m",
            "Gefälleestrich in Nassräumen, {n} m²",
            "Verbundestrich Industrieboden, {n} m²",
        ],
        "norms": ["DIN 18353", "DIN 18560", "KG 352"],
    },
    "fliesen": {
        "title": ["Fliesenarbeiten", "Fliesen- und Plattenarbeiten", "Fliesenleger", "Wand- und Bodenfliesen"],
        "items": [
            "Bodenfliesen Feinsteinzeug 60x60, im Dünnbett, {n} m²",
            "Wandfliesen 30x60 in Bädern, {n} m²",
            "Verbundabdichtung in Duschbereichen, {n} m²",
            "Sockelfliesen, {n} m",
            "Bewegungsfugen elastisch, {n} m",
            "Großformatplatten 120x120, {n} m²",
        ],
        "norms": ["DIN 18352", "KG 352", "KG 345"],
    },
    "maler": {
        "title": ["Malerarbeiten", "Maler- und Lackierarbeiten", "Anstricharbeiten", "Beschichtungsarbeiten"],
        "items": [
            "Dispersionsanstrich auf Putz, Nassabrieb Klasse 2, {n} m²",
            "Spachtelung Q3 auf GK-Flächen, {n} m²",
            "Lackierung von Stahlzargen, {n} Stk",
            "Glasvlies tapezieren und streichen, {n} m²",
            "Fassadenanstrich Silikonharzfarbe, {n} m²",
            "Bodenbeschichtung Epoxidharz in Technikräumen, {n} m²",
        ],
        "norms": ["DIN 18363", "KG 345", "KG 335"],
    },
    "bodenbelag": {
        "title": ["Bodenbelagsarbeiten", "Bodenbeläge", "Parkettarbeiten", "Bodenbelag"],
        "items": [
            "Linoleum 2,5 mm verkleben, {n} m²",
            "Mehrschichtparkett Eiche, {n} m²",
            "Kautschukbelag in Fluren, {n} m²",
            "Teppichfliesen 50x50, {n} m²",
            "Untergrund spachteln und grundieren, {n} m²",
            "Sockelleisten Holz, {n} m",
            "Vinyl-Designbelag, {n} m²",
        ],
        "norms": ["DIN 18365", "DIN 18356", "KG 352"],
    },
    "tischler": {
        "title": ["Tischlerarbeiten", "Innentüren", "Schreinerarbeiten", "Innenausbau Holz"],
        "items": [
            "Innentüren Röhrenspan mit Stahlzarge, {n} Stk",
            "Einbauschränke nach Zeichnung, {n} Stk",
            "Empfangstresen, Sonderanfertigung, {n} Stk",
            "Fensterbänke innen Holz, {n} m",
            "Brandschutztüren T30 Holz, {n} Stk",
            "Wandverkleidung Holzwerkstoff, {n} m²",
        ],
        "norms": ["DIN 18355", "KG 344", "KG 371"],
    },
    "heizung": {
        "title": ["Heizungsinstallation", "Heizungsanlagen", "Heizung", "Wärmeversorgung", "Heizungstechnik"],
        "items": [
            "Luft-Wasser-Wärmepumpe 40 kW inkl. Pufferspeicher, {n} Stk",
            "Fußbodenheizung Systemplatte, {n} m²",
            "Heizkörper Kompakt Typ 22, {n} Stk",
            "Heizungsrohre C-Stahl gedämmt, {n} m",
            "Hydraulischer Abgleich, {n} Stk",
            "Fernwärme-Übergabestation, {n} Stk",
        ],
        "norms": ["DIN 18380", "KG 420", "GEG"],
    },
    "sanitaer": {
        "title": ["Sanitärinstallation", "Sanitärarbeiten", "Gas-, Wasser- und Abwasserinstallation", "Sanitär"],
        "items": [
            "Trinkwasserleitungen Edelstahl, {n} m",
            "Abwasserleitungen HT DN 100 schallgedämmt, {n} m",
            "WC-Anlagen wandhängend inkl. Vorwandelement, {n} Stk",
            "Waschtische mit Armatur, {n} Stk",
            "Hebeanlage für Fäkalien, {n} Stk",
            "Duschrinnen, {n} Stk",
        ],
        "norms": ["DIN 18381", "KG 410", "DIN 1988"],
    },
    "lueftung": {
        "title": ["Lüftungsanlagen", "Raumlufttechnik", "Lüftungstechnik", "RLT-Anlagen"],
        "items": [
            "RLT-Gerät mit Wärmerückgewinnung, 8.000 m³/h, {n} Stk",
            "Luftkanäle verzinkt, {n} m²",
            "Brandschutzklappen K90, {n} Stk",
            "Wickelfalzrohr DN 200, {n} m",
            "Volumenstromregler, {n} Stk",
            "Zuluftdurchlässe Drallauslass, {n} Stk",
        ],
        "norms": ["DIN 18379", "KG 430", "DIN EN 16798"],
    },
    "elektro": {
        "title": ["Elektroinstallation", "Elektrotechnik", "Starkstromanlagen", "Elektroarbeiten"],
        "items": [
            "NYM-J 3x1,5 mm² unter Putz, {n} m",
            "Unterverteilungen bestücken, {n} Stk",
            "LED-Langfeldleuchten, {n} Stk",
            "Kabeltrassen Gitterrinne, {n} m",
            "Brandmeldeanlage mit Meldern, {n} Stk",
            "Erdungs- und Blitzschutzanlage, {n} m",
            "Schalter und Steckdosen, {n} Stk",
        ],
        "norms": ["DIN 18382", "KG 440", "KG 450", "VDE 0100"],
    },
    "aufzug": {
        "title": ["Aufzugsanlage", "Aufzugsanlagen", "Personenaufzug", "Fördertechnik"],
        "items": [
            "Personenaufzug 1.000 kg, 13 Personen, {n} Haltestellen",
            "Maschinenraumloser Seilaufzug, {n} Stk",
            "Notrufsystem und Fernüberwachung, {n} Stk",
            "Schachtgerüst und Montage, {n} Stk",
        ],
        "norms": ["DIN 18385", "KG 461", "EN 81-20"],
    },
    "geruest": {
        "title": ["Gerüstarbeiten", "Gerüstbau", "Fassadengerüst", "Arbeitsgerüst"],
        "items": [
            "Fassadengerüst LK 3, Breitenklasse W09, {n} m²",
            "Vorhaltung über 4 Wochen hinaus, {n} m²",
            "Schutznetze, {n} m²",
            "Treppenturm, {n} Stk",
            "Dachfanggerüst, {n} m",
        ],
        "norms": ["DIN 18451", "DIN EN 12811", "KG 391"],
    },
    "abbruch": {
        "title": ["Abbrucharbeiten", "Rückbau", "Abbruch- und Rückbauarbeiten", "Entkernung", "Schadstoffsanierung"],
        "items": [
            "Entkernung Innenausbau, {n} m²",
            "Abbruch Stahlbetonwände, {n} m³",
            "Asbesthaltige Bauteile nach TRGS 519 ausbauen, {n} m²",
            "Bauschutt sortenrein trennen und entsorgen, {n} t",
            "Estrich und Bodenbeläge entfernen, {n} m²",
            "Betonsägearbeiten, {n} m",
        ],
        "norms": ["DIN 18459", "KG 210", "TRGS 519"],
    },
    "aussenanlagen": {
        "title": ["Außenanlagen", "Garten- und Landschaftsbau", "Pflasterarbeiten", "Freianlagen", "GaLaBau"],
        "items": [
            "Betonsteinpflaster 8 cm, {n} m²",
            "Rasenansaat inkl. Fertigstellungspflege, {n} m²",
            "Bordsteine Beton, {n} m",
            "Baumpflanzungen Hochstamm, {n} Stk",
            "Spielplatzgeräte, {n} Stk",
            "Rigolen und Versickerung, {n} m",
        ],
        "norms": ["DIN 18318", "DIN 18320", "KG 500"],
    },
}

# Words that appear in many trades' texts and say nothing about the trade on their own.
COMMON = [
    "inkl. Baustelleneinrichtung",
    "nach Angabe der Bauleitung",
    "gemäß Leistungsbeschreibung",
    "Ausführung in mehreren Bauabschnitten",
    "inkl. Nebenarbeiten",
    "einschließlich Aufmaß und Dokumentation",
    "Termin gemäß Bauzeitenplan",
    "Abrechnung nach Aufmaß",
    "Bauvorhaben im laufenden Betrieb",
    "inkl. Entsorgung des Verpackungsmaterials",
    "Anschlüsse an angrenzende Bauteile",
    "Beschichtung nach Wahl",
    "Abdichtung der Anschlüsse",
    "Gerüst wird bauseits gestellt",
]

ABBREV = {
    "Trockenbauarbeiten": "TB-Arbeiten",
    "Raumlufttechnik": "RLT",
    "Elektroinstallation": "ELT",
    "Heizungsinstallation": "HZG",
    "Sanitärinstallation": "SAN",
    "Wärmedämmverbundsystem": "WDVS",
}


def lot_text(trade: str, rng: random.Random, style: str, lot_no: int) -> tuple[str, str]:
    """(title, text) of one lot. style: terse | normal | long; buyers keep their style."""
    v = VOCAB[trade]
    title = rng.choice(v["title"])
    if rng.random() < 0.15:
        title = ABBREV.get(title, title)
    prefix = rng.choice([f"Los {lot_no:02d} – ", f"Los {lot_no} ", f"LV {lot_no:02d} ", f"Gewerk {lot_no * 100} ", ""])
    n_items = {"terse": 1, "normal": rng.randint(2, 3), "long": rng.randint(3, 5)}[style]
    items = rng.sample(v["items"], min(n_items, len(v["items"])))
    lines = [it.format(n=_qty(rng)) for it in items]
    if style != "terse" and rng.random() < 0.6:
        lines.append(rng.choice(v["norms"]))
    if rng.random() < {"terse": 0.2, "normal": 0.5, "long": 0.8}[style]:
        lines.append(rng.choice(COMMON))
    if style == "terse" and rng.random() < 0.5:
        return prefix + title, lines[0]
    rng.shuffle(lines)
    return prefix + title, "\n".join(lines)


def _qty(rng: random.Random) -> str:
    n = rng.choice([rng.randint(2, 40), rng.randint(40, 900), rng.randint(900, 9000)])
    return f"{n:,}".replace(",", ".")

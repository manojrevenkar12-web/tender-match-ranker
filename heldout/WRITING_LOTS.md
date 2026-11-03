# Writing a held-out set of tender lots

A held-out set tests how the platform reads **which trade a lot belongs to** from the text a general
contractor writes into a tender. It must be written by someone who has **not seen the code or the
training data**. Read only this file and `config/trades.yaml`. Do not open `tmr/`, `tests/`, `data/`,
`reports/`, `runs/`, `web/` or other sets in `heldout/`.

Write `heldout/<set>/lots.yaml`: a list of 150 to 200 lots, at least 5 per trade in `config/trades.yaml`.

```yaml
- id: lot-001
  title: "Los 07 – Innenputz"                     # the lot's title as a buyer writes it
  text: |                                         # the short description, 1–6 lines, German
    Maschinenputz Q2 auf Mauerwerk, ca. 2.400 m², inkl. Eckschutzschienen ...
  trade: putz                                     # the key from config/trades.yaml
  city: Leipzig                                   # where the project is
  note: "…"                                       # optional: why this one is hard
```

Write the way real German tenders are written, by many different buyers: lot numbers ("Los 3",
"LV 12", "Gewerk 400"), abbreviations (WDVS, GK, TGA, HLS, RLT, ELT, BSH, KS, WU-Beton), norms
(DIN 18340 …), DIN 276 cost groups (KG 330, KG 440 …), quantities and units, product names written
generically, typos, terse one-liners and long specs. Include:

- **Easy lots** where the trade is named outright.
- **Hard lots** where it is not: the work is described only by what is done or built
  ("Ständerwände CW 75 doppelt beplankt" is Trockenbau; "Sockelabdichtung mit Bitumenbahn" may be
  Dachabdichtung or Rohbau depending on context: decide as a site manager would and say why in
  `note`).
- **Near-misses** between neighbouring trades: Putz vs Maler vs Trockenbau; Heizung vs Sanitär vs
  Lüftung (HLS lots: choose the main trade); Fenster/Metallbau vs Tischler; Estrich vs Bodenbelag;
  Dachdecker vs Klempner vs Zimmerer; Erdarbeiten vs Außenanlagen vs Abbruch.
- **Mixed lots** that bundle two trades: label the trade most of the value is in, and say so in
  `note`.

Do not invent trades outside `config/trades.yaml`. Also write `heldout/<set>/README.md` (who wrote it,
from what, any ambiguity and the choice you made) and `heldout/<set>/STATUS` containing `blind`.

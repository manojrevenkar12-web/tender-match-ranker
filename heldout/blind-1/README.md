# Held-out set `blind-1`

Written on 2026-11-03 by a Claude subagent that had not seen the platform's code, training data,
reports or any other held-out set. It read only two files:

- `heldout/WRITING_LOTS.md` (instructions and format)
- `config/trades.yaml` (the 22 trade keys)

No repository command was run while writing it. The lots are hand-written from general knowledge of
German tendering (VOB/C ATVs, DIN 276 cost groups, StLB-Bau Leistungsbereiche, GAEB habits), in the
style of many different buyers. Order is shuffled; ids are `lot-001` … `lot-196`.

## Contents

196 lots, 7 to 11 per trade. Roughly 29 % easy (trade named outright, or the DIN 276 KG / StLB LB
number makes it obvious), 37 % hard (trade only from the work described, terse lines, typos), 34 %
near-miss or mixed. Every hard, near-miss or mixed lot has a `note` that starts with `hard:`,
`near-miss <a> vs <b>:` or `mixed:` and says why the label was chosen.

## Ambiguities and the choice made

- Bauwerksabdichtung (DIN 18336 is filed under `dachdecker`): basement waterproofing done before backfill inside the Rohbau LV → `rohbau`; upstands and Sockel details of a flat roof → `dachdecker`.
- Metal roof and wall coverings (standing seam copper/zinc) → `klempner` (DIN 18339), not `dachdecker`.
- A separate lot for outside window sills → `klempner`; outside sills bundled into a window lot → `fenster`; inside sills → `tischler`.
- Exterior windows of any material (wood, wood-alu, heritage wood windows) → `fenster`, even though a joiner may build them.
- Fire doors: steel → `fenster` (Metallbau); wooden T30 doors → `tischler`.
- Load-bearing steel escape stairs, work platforms and transfer beams for openings in existing walls → `stahlbau`; railings, gates, grilles → `fenster`.
- External sun shading (Raffstores) has no key → `fenster`.
- Glass partitions in offices → `fenster` (glazing/Metallbau), not `trockenbau`.
- Raised access floors and board fire encasement of steel → `trockenbau` (both in DIN 18340); intumescent fire coating → `maler`.
- Trockenputz (boards glued to masonry) and Q4 skim on plasterboard → `trockenbau`; plaster on lath (Rabitz) → `putz`.
- Insulation, vapour control and GK lining of a loft between rafters → `trockenbau`; rafter build-up, sheathing, dormer framing → `zimmerer`.
- Exterior timber cladding → `zimmerer`; veneered interior panelling → `tischler`.
- Resin floor coatings (OS 8 in car parks) have no own key → `maler` (Beschichtung).
- Sports floors → `bodenbelag`; refinishing old floorboards → `bodenbelag`.
- Ground-polished cement screed used as the finished floor, hard-aggregate wearing screed, mastic asphalt screed → `estrich`.
- Levelling compound followed by a floor finish in the same lot → `bodenbelag`.
- Natural stone stairs and slabs in mortar bed (no stone key) → `fliesen`.
- Ceramic slabs on pedestals on balconies → `fliesen`; slabs on gravel on ground-level terraces → `aussenanlagen`.
- Green roofs: waterproofing plus extensive greening → `dachdecker`; intensive landscaping on an already waterproofed garage deck → `aussenanlagen`.
- Trench excavation where pipes are laid by another trade → `erdarbeiten`; the drainage pipes under the slab themselves → `sanitaer`.
- Grading a sub-base for later paving with no surfacing → `erdarbeiten`; sub-base plus surfacing → `aussenanlagen`.
- Removing contaminated soil after the building is gone → `erdarbeiten`; breaking up asphalt, kerbs and foundations → `abbruch`.
- Concrete sawing and core drilling only → `abbruch`; new openings with lintels and propping in masonry → `rohbau`.
- Removing an asbestos roof covering with no new covering → `abbruch`.
- Shoring (Verbau) and open dewatering have no key → `erdarbeiten` when they come with the excavation.
- Siphonic roof drainage inside the building → `sanitaer`; gutters and downpipes to the standpipe → `klempner`.
- Domestic hot water (fresh water station, legionella protection), gas pipework and wet fire-fighting lines → `sanitaer`.
- Pipe insulation (no key for DIN 18421) → the trade whose pipes it insulates (`heizung` here).
- Cooling and split units (no own key) → `lueftung` when bundled with ventilation.
- Mechanical smoke extraction → `lueftung`; fire alarm, lightning protection, PV, EV charging → `elektro`.
- Escalators and platform lifts → `aufzug` (DIN 18385); a steel-and-glass lift shaft supplied by the lift maker → `aufzug`.
- A temporary weather roof built from system scaffold → `geruest`.
- HLS lots → the trade with most of the value (heating for a house with a heat pump, sanitary for a Kita with 30 fixtures).
- Mixed lots (roofing plus gutters, steel frame plus trapezoidal deck, screed plus fall screed, demolition plus a small excavation, etc.) → the trade with most of the value, stated in `note`.

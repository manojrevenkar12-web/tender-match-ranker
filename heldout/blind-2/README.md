# Held-out set blind-2

Written on 2026-11-03 by a Claude subagent that had not seen the platform's code, its training data,
its reports or any earlier held-out set (including `blind-1`). It read only
`heldout/WRITING_LOTS.md` and `config/trades.yaml`.

- 198 lots, 7–10 per trade, all 22 trade keys.
- Mix: 59 easy (30 %), 79 hard (40 %), 40 near-miss and 20 mixed (30 %). Easy lots have no `note`;
  the others start with `hard:`, `near-miss <a> vs <b>:` or `mixed:`.
- The lots are shuffled with a fixed seed and numbered `lot-001` … `lot-198`, so the order says
  nothing about the trade.
- The lots are written in the styles of many buyers: public clients (Los/LV/TA numbers, DIN 276 cost
  groups, VOB/C norms), housing companies (WE counts, terse one-liners), general contractors
  (GAEB position groups, "bauseits", "siehe Los …") and private developers. Some have typos and
  abbreviations on purpose.

## Ambiguities and the choices made (one line each)

- Sun shading (Raffstore, Rollläden) has no key: labelled `fenster`; motors and wiring are only Elektro if that is all the lot does.
- Building automation (MSR/DDC/GLT, KG 480) has no key: labelled `elektro`.
- Sprinkler systems (KG 474) have no key: labelled `sanitaer` (water pipework under DIN 18381).
- Natural-stone slabs in a mortar bed (DIN 18332) have no key: labelled `fliesen` (Plattenarbeiten).
- Sports floors (DIN EN 14904) have no key: labelled `bodenbelag` when the top layer is a laid covering.
- Shoring (Berliner Verbau, DIN 18303) and dewatering have no key: labelled `erdarbeiten` when tendered with the pit.
- Concrete sawing and coring with no new building: labelled `abbruch`.
- Asbestos and other hazardous-material removal: labelled `abbruch`.
- Structural alterations in existing buildings (new openings with HEB lintels, underpinning): labelled `rohbau`.
- KMB / bitumen waterproofing of basement walls on a housing job: `rohbau`; waterproofing of roofs and used roof decks (DIN 18531/18532): `dachdecker`.
- Watertight concrete (Weiße Wanne): `rohbau`, not waterproofing.
- Standing-seam metal roofs and seamed zinc facades: `klempner`, even though they are roof coverings or cladding.
- Flat-roof outlets bonded into the membrane: `dachdecker`; gutters, downpipes and flashings: `klempner`.
- Trapezoidal sheet laid as structural decking by the steel erector: `stahlbau`.
- A free-standing, structurally designed external escape stair: `stahlbau`; railings, balustrades and gates: `fenster` (Metallbau).
- Fences and gates around the site: `aussenanlagen`, not Metallbau.
- Extensive green roof on an existing root-proof membrane: `aussenanlagen`.
- Topsoil spreading that ends in seeding: `aussenanlagen`; earth moving that stops at a fine grade for others: `erdarbeiten`.
- Breaking out foundations and crushing them for reuse: `abbruch`, not `erdarbeiten`.
- Wooden windows for the building envelope: `fenster`, even when built by a joinery; wooden interior doors, inner sills and interior stairs: `tischler`.
- Steel fire doors, automatic sliding doors and sectional doors: `fenster`.
- Raised access floors (Doppelboden): `trockenbau` (Systemböden under DIN 18340).
- Trockenputz (board on adhesive dabs) and Q4 skim coats on board: `trockenbau`.
- Spray acoustic plaster on carrier boards and clay plaster on reed mats: `putz`.
- Floor preparation (sanding, levelling compound) before a covering: `bodenbelag`; screed repair and hardened industrial screed: `estrich`.
- Resin floor coatings (OS 8 in car parks) and reactive fire-protection coatings on steel: `maler`.
- Underfloor heating pipes without the screed: `heizung`; hot-water unit heaters with no ducts: `heizung`.
- Air-handling units with heating and cooling coils: `lueftung`.
- Installation frames (Vorwand) with WC elements: `sanitaer`; HPL WC cubicles: `tischler`.
- Escalators, platform lifts and dumbwaiters: `aufzug` (Förderanlagen under DIN 18385); a lift-maker's steel shaft goes with the lift.
- Scaffold enclosures for asbestos removal and roof-edge protection: `geruest`.
- PV on a ballasted frame that does not penetrate the roof: `elektro`.
- HLS bundles and other mixed lots: the trade with most of the value, as stated in each `note`.

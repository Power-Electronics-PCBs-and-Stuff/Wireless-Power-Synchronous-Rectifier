# PCB layout generator (scripted, KiCad 10)

The board in `../../Synchronous Rectifier.kicad_pcb` was produced by these scripts, run with KiCad's bundled
Python (`C:\Program Files\KiCad\10.0\bin\python.exe`). Re-running regenerates the whole layout from an
un-routed board that has the footprints and nets from the schematic.

Workflow when the schematic changes:
1. In KiCad: Tools -> Update PCB from Schematic (keeps nets/footprints in sync). Close the PCB editor.
2. Copy the PCB as the build input (the scripts call it `base2.kicad_pcb`):
   `cp "../../Synchronous Rectifier.kicad_pcb" base2.kicad_pcb`
   (new reference designators need an entry in the `PL` placement table in `build_pcb.py`).
3. `./multi.sh` tries several routing orders and keeps the first fully-routed result (`v*.kicad_pcb`).
4. `python finish.py <board> sample_stackup_source.kicad_pcb <project.kicad_pro>` writes the 4-layer
   stackup (2 oz outer) into the board and the net classes/rules into the project file.
5. `"C:\Program Files\KiCad\10.0\bin\python.exe" check_board.py <board> --drc` for a summary + kicad-cli DRC.
6. Copy the board over the project PCB (back it up first), then run the kicad-happy analyzers
   (`analyze_pcb.py --full --schematic ...`, `cross_analysis.py`, `analyze_emc.py`) with `--analysis-dir analysis/`.

Files: `build_pcb.py` (placement table, zones, via arrays, power copper, GND-pocket stitching, reference text),
`router.py` (grid A* router on F/B with vias; 5V drops into the In1 plane), `finish.py`, `check_board.py`,
`islands.py` (lists zone fill islands), `drcsum.py` (groups a kicad-cli DRC report), `render.sh`/`crop.sh`
(PDF -> PNG previews via pdftoppm).

## v30 additions (2026-11-08)
- `run_v30.sh` = multi-seed routed build + finish + DRC; `post_v30.sh` installs the board when DRC is clean and runs the
  kicad-happy analyzers; `multi.sh` picks the best fully routed seed by `score.py`.
- `current_check.py <board>`: copper width per layer across named cut lines -> IPC-2221 ampacity table (edit `CUTS`).
- `pair_check.py <board>`: lengths of the signal pairs, remaining right-angle corners, decoupling-cap axis vs. pin.
- In `build_pcb.py`: `place_near`/`place_between` (decoupling and bootstrap caps), `pair_testpoints` (GND test point next
  to every signal test point, `FIXED_GND` for hand-placed ones), `chamfer_tracks` (45-degree mitres after routing),
  hand-routed G1/G3 gate tracks, bridge caps C28/C29/C30/C54 under the FET columns on the `OUTB` Out+ pour.

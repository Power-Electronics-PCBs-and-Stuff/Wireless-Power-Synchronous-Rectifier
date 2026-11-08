#!/bin/bash
# try several routing orders; among fully routed boards keep the one with the best score.py (else the fewest unrouted pads)
cd "$(dirname "$0")"
PY="/c/Program Files/KiCad/10.0/bin/python.exe"
best=""; bestn=999; bests=99999
for seed in 0 1 2 3 4; do
  ROUTE_SEED=$seed "$PY" build_pcb.py base2.kicad_pcb try_$seed.kicad_pcb 2>&1 | grep -v "duplicate image\|GetWidth called" | grep "saved\|   unrouted\|Traceback\|Error" > try_$seed.log
  if grep -q "^saved" try_$seed.log; then n=$(grep -o "unrouted \[.*\]" try_$seed.log | grep -o "('" | wc -l); else n=999; echo "seed $seed BUILD FAILED"; fi
  sc=99999; if [ "$n" -eq 0 ]; then sc=$("$PY" score.py try_$seed.kicad_pcb 2>/dev/null | tail -1); fi
  echo "seed $seed unrouted $n score $sc"
  if [ "$n" -lt "$bestn" ] || { [ "$n" -eq "$bestn" ] && [ "$n" -eq 0 ] && [ "$(python -c "print(int(float('$sc') < float('$bests')))")" = "1" ]; }; then bestn=$n; bests=$sc; best=$seed; fi
done
echo "best seed $best (unrouted $bestn, score $bests)"; cp try_$best.kicad_pcb v30.kicad_pcb; cp try_$best.log v30.log

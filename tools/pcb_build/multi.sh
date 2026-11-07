#!/bin/bash
# try several routing orders, keep the one with the fewest unrouted pads
cd "$(dirname "$0")"
best=""; bestn=999
for seed in 0 1 2 3 4; do
  ROUTE_SEED=$seed "/c/Program Files/KiCad/10.0/bin/python.exe" build_pcb.py base2.kicad_pcb try_$seed.kicad_pcb 2>&1 | grep -v "duplicate image\|GetWidth called" | grep "saved\|   unrouted" > try_$seed.log
  if grep -q "^saved" try_$seed.log; then n=$(grep -o "unrouted \[.*\]" try_$seed.log | grep -o "('" | wc -l); else n=999; echo "seed $seed BUILD FAILED"; fi
  echo "seed $seed unrouted $n"
  if [ "$n" -lt "$bestn" ]; then bestn=$n; best=$seed; fi
  if [ "$n" -eq 0 ]; then break; fi
done
echo "best seed $best ($bestn)"; cp try_$best.kicad_pcb v25.kicad_pcb; cp try_$best.log v25.log

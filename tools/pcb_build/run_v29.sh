#!/bin/bash
cd "$(dirname "$0")"
PY="/c/Program Files/KiCad/10.0/bin/python.exe"
"$PY" build_pcb.py base2.kicad_pcb try_place.kicad_pcb --no-route 2>&1 | grep -v "duplicate image\|GetWidth" | grep -i "place_\|fix_tp\|Traceback\|Error\|saved"
./multi.sh
cat v29.log
cp "/c/Users/Vedant/Documents/KiCad/Guad_Rectifier/Synchronous Rectifier/Synchronous Rectifier.kicad_pro" v29.kicad_pro
"$PY" finish.py v29.kicad_pcb sample.kicad_pcb v29.kicad_pro 2>&1 | grep -v "duplicate image\|GetWidth" | tail -1
"$PY" check_board.py v29.kicad_pcb --drc 2>&1 | grep -v "duplicate image\|GetWidth" | grep -A12 "Top 15 rule ids"
python -I drcsum.py v29.kicad_pcb.drc.rpt 2>/dev/null | grep -v "silk" | grep "^\s*\[" | head -30

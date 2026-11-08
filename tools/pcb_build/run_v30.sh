#!/bin/bash
cd "$(dirname "$0")"
PY="/c/Program Files/KiCad/10.0/bin/python.exe"
./multi.sh
cat v30.log
cp "/c/Users/Vedant/Documents/KiCad/Guad_Rectifier/Synchronous Rectifier/Synchronous Rectifier.kicad_pro" v30.kicad_pro
"$PY" finish.py v30.kicad_pcb sample.kicad_pcb v30.kicad_pro 2>&1 | grep -v "duplicate image\|GetWidth" | tail -1
"$PY" check_board.py v30.kicad_pcb --drc 2>&1 | grep -v "duplicate image\|GetWidth" | grep -A14 "Top 15 rule ids"
python -I drcsum.py v30.kicad_pcb.drc.rpt 2>/dev/null | grep -v "silk" | grep "^\s*\[" | head -40
echo BUILD-DONE

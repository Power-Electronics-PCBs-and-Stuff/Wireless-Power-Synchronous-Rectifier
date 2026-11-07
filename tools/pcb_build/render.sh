#!/bin/bash
# render.sh <board.kicad_pcb> <prefix>
K="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
for L in "F.Cu,F.SilkS,Edge.Cuts" "B.Cu,B.SilkS,Edge.Cuts" "In1.Cu,Edge.Cuts" "In2.Cu,Edge.Cuts"; do
  n=$(echo $L | cut -d, -f1)
  timeout 120 "$K" pcb export pdf -o "$2_$n.pdf" -l "$L" --mode-single "$1" >/dev/null 2>&1
  pdftoppm -png -r 150 -singlefile "$2_$n.pdf" "$2_$n" 2>/dev/null
done
ls "$2"_*.png

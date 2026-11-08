#!/bin/bash
# install v30 if DRC is clean (only the known library leftovers), then run the kicad-happy analyzers on the project
cd "$(dirname "$0")"
PRJ="/c/Users/Vedant/Documents/KiCad/Guad_Rectifier/Synchronous Rectifier"
S=/c/Users/Vedant/.claude/plugins/cache/kicad-happy/kicad-happy/3.0.1/skills
if ! grep -q "Found 0 unconnected" v30.kicad_pcb.drc.rpt; then echo "NOT INSTALLED: unconnected items"; exit 0; fi
bad=$(python -I drcsum.py v30.kicad_pcb.drc.rpt | grep "^\s*\[" | grep -v "silk\|U4\|IC2" | wc -l)
if [ "$bad" != "0" ]; then echo "NOT INSTALLED: $bad unexpected DRC items"; python -I drcsum.py v30.kicad_pcb.drc.rpt | grep "^\s*\[" | grep -v "silk\|U4\|IC2"; exit 0; fi
if ls "$PRJ"/~*.kicad_pcb.lck >/dev/null 2>&1; then echo "NOT INSTALLED: PCB open in KiCad"; exit 0; fi
ts=$(date +%Y%m%d_%H%M); cp "$PRJ/Synchronous Rectifier.kicad_pcb" backup_pcb_$ts.kicad_pcb
cp v30.kicad_pcb "$PRJ/Synchronous Rectifier.kicad_pcb"; cp v30.kicad_pcb base_installed.kicad_pcb; echo "installed v30 (backup backup_pcb_$ts)"
cd "$PRJ"
python "$S/kicad/scripts/analyze_pcb.py" "Synchronous Rectifier.kicad_pcb" --full --schematic analysis/2026-11-06_2334/schematic.json --analysis-dir analysis/ 2>&1 | tail -1
RUN=$(ls -dt analysis/*/ | head -1); echo "run $RUN"
cp analysis/2026-11-06_2334/schematic.json "$RUN/schematic.json" 2>/dev/null
python "$S/kicad/scripts/cross_analysis.py" --schematic "$RUN/schematic.json" --pcb "$RUN/pcb.json" --analysis-dir analysis/ 2>&1 | tail -1
python "$S/emc/scripts/analyze_emc.py" --schematic "$RUN/schematic.json" --pcb "$RUN/pcb.json" --analysis-dir analysis/ 2>&1 | tail -1
python "$S/kicad/scripts/analyze_thermal.py" -s "$RUN/schematic.json" -p "$RUN/pcb.json" --analysis-dir analysis/ 2>&1 | tail -1
python "$S/kicad/scripts/summarize_findings.py" analysis/ --top 25 --severity warning 2>&1 | head -60
echo POST-DONE

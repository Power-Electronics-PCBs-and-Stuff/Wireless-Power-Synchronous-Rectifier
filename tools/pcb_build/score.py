"""score.py <board>: routing-quality score for picking a seed: OPA656 input mismatch + G2 + G4 + +IN length (mm, lower is better)"""
import sys, pcbnew
from collections import defaultdict
b = pcbnew.LoadBoard(sys.argv[1]); L = defaultdict(float)
for t in b.GetTracks():
    if t.GetClass() == 'PCB_TRACK': L[t.GetNetname()] += pcbnew.ToMM(t.GetLength())
print(round(abs(L['Net-(IC3-+IN)'] - L['Net-(IC3--IN)']) + L['G2'] + L['G4'] + L['Net-(IC3-+IN)'] + L['Net-(U1-PWM)'] * 0.3, 1))

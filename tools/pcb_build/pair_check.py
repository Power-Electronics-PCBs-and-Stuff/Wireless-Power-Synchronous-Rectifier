"""pair_check.py <board.kicad_pcb>
Routed length (tracks + vias) of the signal pairs that should match, right-angle corner count, and cap orientation
relative to the pin each decoupling cap serves.
"""
import sys, math
import pcbnew
from collections import defaultdict

mm = pcbnew.ToMM
board = pcbnew.LoadBoard(sys.argv[1])
length = defaultdict(float); vias = defaultdict(int)
for t in board.GetTracks():
    n = t.GetNetname()
    if t.GetClass() == 'PCB_TRACK':
        length[n] += mm(t.GetLength())
    elif t.GetClass() == 'PCB_VIA':
        vias[n] += 1
PAIRS = [('OPA656 inputs', 'Net-(IC3-+IN)', 'Net-(IC3--IN)'),
         ('gate drives, left half bridge', 'G1', 'G3'),
         ('gate drives, right half bridge', 'G2', 'G4'),
         ('switch nodes', 'S1', 'S2'),
         ('driver PWM inputs', 'Net-(S1_Gate_Driver1-PWM)', 'Net-(U1-PWM)'),
         ('comparator references', '2.5Va', '2.5Vb')]
print(f"{'pair':34} {'net A':28} {'mm':>7} {'vias':>4} | {'net B':28} {'mm':>7} {'vias':>4} | delta")
for label, a, b in PAIRS:
    la, lb = length.get(a, 0.0), length.get(b, 0.0)
    d = abs(la - lb); pct = 100 * d / max(la, lb, 1e-9)
    print(f'{label:34} {a:28} {la:7.2f} {vias.get(a, 0):4} | {b:28} {lb:7.2f} {vias.get(b, 0):4} | {d:5.2f} mm ({pct:4.1f} %)')

# right-angle corners between track segments of the same net/layer
ends = defaultdict(list)
for t in board.GetTracks():
    if t.GetClass() != 'PCB_TRACK':
        continue
    for v in (t.GetStart(), t.GetEnd()):
        ends[(t.GetLayer(), round(mm(v.x), 3), round(mm(v.y), 3))].append(t)
right = 0; corners = 0; examples = []
for (layer, x, y), ts in ends.items():
    if len(ts) != 2 or ts[0].GetNetCode() != ts[1].GetNetCode():
        continue
    def away(t):
        s, e = t.GetStart(), t.GetEnd()
        o = e if (round(mm(s.x), 3), round(mm(s.y), 3)) == (x, y) else s
        return (mm(o.x) - x, mm(o.y) - y)
    da, db = away(ts[0]), away(ts[1]); la, lb = math.hypot(*da), math.hypot(*db)
    if la < 1e-6 or lb < 1e-6:
        continue
    corners += 1
    if abs(da[0] * db[0] + da[1] * db[1]) <= 1e-3 * la * lb:
        right += 1
        if len(examples) < 12:
            examples.append((ts[0].GetNetname(), layer, x, y, round(mm(ts[0].GetWidth()), 2)))
print(f'\ntrack corners: {corners}, right angles left: {right}')
for e in examples:
    print('   ', e)

# decoupling caps: axis must point at the IC pin they serve (cap "parallel to its connection")
CAPS = [('C17', 'VCO1', '16'), ('C18', 'U2', '5'), ('C6', 'U2', '4'), ('C36', 'U3', '5'), ('C25', 'U3', '4'), ('C48', 'IC3', '7'), ('C49', 'IC3', '4'),
        ('C12', 'IC3', '7'), ('C38', 'IC2', '4'), ('C39', 'IC2', '1'), ('C7', 'U1', '16'), ('C8', 'U1', '11'), ('C32', 'U1', '6'), ('C26', 'U4', '1'),
        ('C16', 'U4', '6'), ('C20', 'U11', '5'), ('C10', 'U10', '5'), ('C61', 'S1_Gate_Driver1', '11'), ('C52', 'S1_Gate_Driver1', '3'),
        ('C24', 'S1_Gate_Driver1', '6'), ('C62', 'U9', '11'), ('C53', 'U9', '3'), ('C31', 'U9', '6'),
        ('C28', 'Q1', '3'), ('C29', 'Q1', '3'), ('C30', 'Q3', '3'), ('C54', 'Q3', '3')]
print('\ncap orientation vs. its pin (0 deg = cap axis points at the pin):')
for cap, ic, pin in CAPS:
    c = board.FindFootprintByReference(cap); icf = board.FindFootprintByReference(ic)
    pp = [q for q in icf.Pads() if q.GetNumber() == pin][0].GetPosition()
    pads = list(c.Pads())
    # pad of the cap on the same net as the IC pin
    same = [q for q in pads if q.GetNetCode() == [q for q in icf.Pads() if q.GetNumber() == pin][0].GetNetCode()]
    if not same:
        print(f'  {cap:4} no pad shares a net with {ic}.{pin}'); continue
    q = same[0]; other = [r for r in pads if r is not q][0] if len(pads) > 1 else q
    ax = (mm(q.GetPosition().x) - mm(other.GetPosition().x), mm(q.GetPosition().y) - mm(other.GetPosition().y))
    to = (mm(pp.x) - mm(q.GetPosition().x), mm(pp.y) - mm(q.GetPosition().y))
    d = math.hypot(*to); ang = math.degrees(math.acos(max(-1, min(1, (ax[0] * to[0] + ax[1] * to[1]) / (math.hypot(*ax) * d + 1e-9)))))
    print(f'  {cap:4} -> {ic}.{pin:3} pad-to-pin {d:4.1f} mm  axis-to-pin angle {ang:5.1f} deg')

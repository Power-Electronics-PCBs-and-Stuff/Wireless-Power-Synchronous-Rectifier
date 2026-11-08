"""current_check.py <board.kicad_pcb>
Copper cross-section and IPC-2221 ampacity (20 degC rise) of the power paths, measured on the *filled* board:
for each named cut line the script samples the copper of the net on every layer (zone fills + tracks + pads)
and converts the copper width per layer into a current rating. Outer layers 2 oz (0.0696 mm), inner 1 oz (0.0348 mm).
"""
import sys, math
import pcbnew

F, IN1, IN2, B = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu
LAYERS = [(F, 'F.Cu', 0.0696, 0.048), (IN1, 'In1.Cu', 0.0348, 0.024), (IN2, 'In2.Cu', 0.0348, 0.024), (B, 'B.Cu', 0.0696, 0.048)]
mm = pcbnew.ToMM
board = pcbnew.LoadBoard(sys.argv[1])
nets = {n.GetNetname(): n.GetNetCode() for n in board.GetNetsByName().values()}


def ipc(width_mm, thick_mm, k, dT=20.0):
    a_mil2 = width_mm * thick_mm / (0.0254 ** 2)
    return 0.0 if a_mil2 <= 0 else k * dT ** 0.44 * a_mil2 ** 0.725


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def copper_width(netcode, layer, a, b, step=0.02):
    """length of the cut a-b that lies on copper of `netcode` on `layer`"""
    polys = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != netcode or not z.IsOnLayer(layer):
            continue
        polys.append(z.GetFilledPolysList(layer))
    tracks = [(mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()) / 2)
              for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetCode() == netcode and t.GetLayer() == layer]
    pads = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetCode() == netcode and p.IsOnLayer(layer)]
    L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(L / step))
    hit = 0
    for i in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        v = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
        on = any(ps.Contains(v) for ps in polys) or any(seg_d(x, y, *t[:4]) <= t[4] for t in tracks) or any(p.HitTest(v) for p in pads)
        hit += on
    return L * hit / (n + 1)


# (label, net, cut start, cut end, current that must pass this cut)
CUTS = [
    ('Out+ bus, mid-way to the XT60 (y=100)',        'Out+', (81.0, 100.0), (88.0, 100.0), 10.0),
    ('Out+ bus, above J1 pad (y=102)',               'Out+', (81.0, 102.0), (88.0, 102.0), 10.0),
    ('Out+ neck, bulk caps -> bridge (x=95)',        'Out+', (95.0, 75.0), (95.0, 84.0), 10.0),
    ('Out+ band/column entry (y=81, x101-119)',      'Out+', (101.0, 81.0), (119.0, 81.0), 10.0),
    ('Out+ under the bridge (y=85, x102-118)',       'Out+', (102.0, 85.0), (118.0, 85.0), 10.0),
    ('GND island -> main pour (y=100.5, x102-118)',  'GND', (102.0, 100.5), (118.0, 100.5), 10.0),
    ('GND left of the S1 driver island (x=86, y83-101)', 'GND', (86.0, 83.0), (86.0, 101.0), 10.0),
    ('Tank: coil -> C58 (y=58, x98-108)',            'Net-(ReceiverCoil1-Pin_2)', (98.0, 58.0), (108.0, 58.0), 11.1),
    ('Tank: C58 -> C1 (y=73.75, x96-104)',           'Net-(C1-Pad1)', (96.0, 73.75), (104.0, 73.75), 11.1),
    ('Tank: C1 -> S1 island (y=81, x96-104)',        'S1', (96.0, 81.0), (104.0, 81.0), 11.1),
    ('Tank: coil -> C47 (y=70, x117-125)',           'Is-', (117.0, 70.0), (125.0, 70.0), 11.1),
    ('Tank: C58 pad link (y=68.3, x96-104)',          'Net-(ReceiverCoil1-Pin_2)', (96.0, 68.3), (104.0, 68.3), 11.1),
    ('Tank: C1 pad link (y=79.2, x96-104)',           'S1', (96.0, 79.2), (104.0, 79.2), 11.1),
    ('Tank: C47 pad link (y=78.5, x118-125)',         'S2', (118.0, 78.5), (125.0, 78.5), 11.1),
    ('Out+ J1 pad link (x=83.5, y102-107)',          'Out+', (83.5, 102.0), (83.5, 107.0), 10.0),
    ('Tank: C47 -> S2 island (y=82, x118-125)',      'S2', (118.0, 82.0), (125.0, 82.0), 11.1),
    ('S1 island (y=91, x97-103)',                    'S1', (97.0, 91.0), (103.0, 91.0), 7.9),
    ('S2 island (y=91, x117-123)',                   'S2', (117.0, 91.0), (123.0, 91.0), 7.9),
]
print(f"{'cut':52} {'need A':>6} | " + ' '.join(f'{n:>11}' for _, n, _, _ in LAYERS) + ' |  total A')
for label, net, a, b, need in CUTS:
    if net not in nets:
        print(f'{label:52} net {net} not found'); continue
    tot = 0.0; cols = []
    for layer, name, th, k in LAYERS:
        w = copper_width(nets[net], layer, a, b)
        i = ipc(w, th, k); tot += i
        cols.append(f'{w:4.1f}mm/{i:4.1f}A')
    flag = '' if tot >= need else '   <-- BELOW'
    print(f'{label:52} {need:6.1f} | ' + ' '.join(f'{c:>11}' for c in cols) + f' | {tot:6.1f}A{flag}')

# via budget per net for the layer transitions (0.6/0.3 vias, 25 um plating -> ~2.3 A each at 20 degC, IPC internal)
via_A = ipc(math.pi * 0.3, 0.025, 0.024)
from collections import Counter
cnt = Counter(board.FindNet(v.GetNetCode()).GetNetname() for v in board.GetTracks() if v.GetClass() == 'PCB_VIA')
print(f"\nvia rating ~{via_A:.1f} A each (0.3 mm drill, 25 um plating, 20 degC)")
for n in ('Out+', 'GND', 'S1', 'S2', 'Net-(ReceiverCoil1-Pin_2)', 'Net-(C1-Pad1)', 'Is-'):
    print(f'  {n:28} {cnt.get(n, 0):3} vias  -> {cnt.get(n, 0) * via_A:5.1f} A')

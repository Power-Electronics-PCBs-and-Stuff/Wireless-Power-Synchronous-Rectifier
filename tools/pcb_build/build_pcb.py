"""Build the initial PCB layout for the synchronous rectifier, following Sample/SynchRectifier_v3.

Run with KiCad's python:  python.exe build_pcb.py <in.kicad_pcb> <out.kicad_pcb> [--no-route]
"""
import math
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM

SRC, DST = sys.argv[1], sys.argv[2]
ROUTE = '--no-route' not in sys.argv
board = pcbnew.LoadBoard(SRC)

F, B, IN1, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu
CU4 = (F, IN1, IN2, B)
BOARD = dict(x0=65.1, y0=49.4, x1=216.0, y1=127.0, r=3.0)
BUS = (83.0, 62.0, 86.5, 120.0)      # Out+ bus along the left edge (F/B/In1) from the bulk caps down to the XT60
TANK = (89.0, 49.4, 124.0, 77.5)  # no copper pours under the resonant tank


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def net(name):
    n = board.FindNet(name)
    assert n is not None, name
    return n


# ---------------------------------------------------------------- 0) fix the open op-amp feedback (Is_FB -> Is)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname() == 'Is_FB':
            pad.SetNet(net('Is'))

# ---------------------------------------------------------------- 1) layers / rules
ds = board.GetDesignSettings()
ds.SetCopperLayerCount(4)
ds.m_TrackMinWidth = FromMM(0.2)
ds.m_ViasMinSize = FromMM(0.5)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_CopperEdgeClearance = FromMM(0.5)

# ---------------------------------------------------------------- 2) outline + mounting holes
def outline():
    x0, y0, x1, y1, r = BOARD['x0'], BOARD['y0'], BOARD['x1'], BOARD['y1'], BOARD['r']
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.05)); board.Add(s)
    def arc(a, m, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetArcGeometry(P(*a), P(*m), P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.05)); board.Add(s)
    k = r * (1 - math.sqrt(0.5))
    seg((x0 + r, y0), (x1 - r, y0)); seg((x1, y0 + r), (x1, y1 - r)); seg((x1 - r, y1), (x0 + r, y1)); seg((x0, y1 - r), (x0, y0 + r))
    arc((x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r)); arc((x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1))
    arc((x0 + r, y1), (x0 + k, y1 - k), (x0, y1 - r)); arc((x0, y0 + r), (x0 + k, y0 + k), (x0 + r, y0))


outline()
HOLES = [(68.7, 53.0), (146.4, 53.0), (212.4, 53.0), (68.6, 123.4), (146.4, 123.4), (212.4, 123.4)]
for i, (x, y) in enumerate(HOLES, 1):
    fp = pcbnew.FootprintLoad(r'C:\Program Files\KiCad\10.0\share\kicad\footprints\MountingHole.pretty', 'MountingHole_3.2mm_M3')
    fp.SetReference(f'H{i}'); fp.SetPosition(P(x, y)); fp.Reference().SetVisible(False); board.Add(fp)

# three assembly fiducials around the SMD area
for i, (x, y) in enumerate([(72.5, 56.5), (143.0, 56.5), (75.5, 120.5)], 1):
    fp = pcbnew.FootprintLoad('C:/Program Files/KiCad/10.0/share/kicad/footprints/Fiducial.pretty', 'Fiducial_1mm_Mask2mm')
    fp.SetReference(f'FID{i}'); fp.SetPosition(P(x, y)); fp.Reference().SetVisible(False); board.Add(fp)

# ---------------------------------------------------------------- 3) placement  ref: (x, y, rot, layer)
PL = {
    # --- bridge
    'Q1': (104.0, 86.5, 0, F), 'Q3': (116.0, 86.5, 180, F), 'Q2': (104.0, 95.5, 180, F), 'Q4': (116.0, 95.5, 0, F),
    'C28': (104.6, 91.0, 90, B), 'C29': (107.1, 91.0, 90, B), 'C30': (114.0, 91.0, 90, B), 'C54': (116.5, 91.0, 90, B),   # 2 per half bridge, under the FET columns
    'C19': (84.7, 71.5, 180, F), 'C27': (84.6, 89.5, 180, F),
    'TP19': (103.5, 103.6, 0, F), 'TP22': (119.4, 102.3, 0, F),
    # --- tank / input
    'ReceiverCoil1': (109.0, 62.0, 180, F),
    'C58': (91.5, 66.0, 90, F), 'C1': (91.5, 73.0, 90, F), 'C47': (121.0, 76.0, 90, F),
    'C3': (125.0, 72.5, 0, F), 'C2': (124.5, 80.5, 0, F),
    # --- S1 gate driver (B.Cu) + bootstrap column (F.Cu)
    'S1_Gate_Driver1': (91.7, 93.5, 270, B), 'R41': (96.0, 100.6, 0, B), 'R42': (96.0, 102.4, 0, B),
    'R28': (96.0, 86.5, 0, B), 'C24': (96.0, 88.3, 0, B),
    'C21': (96.3, 104.5, 0, F), 'D5': (92.0, 104.5, 0, F), 'D1': (92.0, 107.0, 0, F), 'C61': (96.3, 107.0, 0, F), 'C52': (96.3, 109.0, 0, F),
    'TP34': (97.6, 106.9, 0, F), 'TP36': (100.8, 108.0, 0, F),
    # --- S2 gate driver (B.Cu) + bootstrap column (F.Cu)
    'U9': (128.7, 93.5, 90, B), 'R1': (131.9, 86.3, 180, B), 'R40': (125.5, 87.5, 90, B),   # R1 flipped: G2 pad on the left so the gate trace arrives along y~86.2 under C4/R45
    'R29': (131.5, 100.6, 0, B), 'C31': (131.5, 102.4, 0, B),
    'C23': (125.0, 84.5, 0, F), 'D6': (124.8, 88.5, 90, F), 'D2': (124.8, 93.5, 90, F), 'C62': (130.5, 98.0, 0, F), 'C53': (130.5, 96.0, 0, F),
    'TP35': (126.2, 84.1, 0, F), 'TP37': (125.8, 102.3, 0, F),
    # --- current sense (top right)
    'R5': (124.3, 75.5, 0, F), 'R6': (127.5, 75.5, 0, F), 'R37': (130.7, 75.5, 0, F),
    'R2': (124.3, 78.0, 0, F), 'R3': (127.5, 78.0, 0, F), 'R4': (130.7, 78.0, 0, F),
    'TP10': (136.6, 78.0, 0, F),
    'IC3': (133.5, 81.5, 0, B), 'R43': (131.9, 83.5, 0, F), 'R44': (134.2, 79.5, 0, F),
    'C4': (128.8, 83.9, 90, F), 'R45': (128.8, 83.9, -90, B), 'C5': (128.8, 80.5, 90, B), 'R46': (128.8, 80.5, -90, F),   # C4/R45 0.6 up: lane for the G2 gate trace
    'C12': (139.0, 83.3, 0, F), 'C48': (135.5, 84.5, 0, F),
    'IC2': (134.5, 74.5, 90, F), 'C40': (134.5, 70.5, 180, F), 'C38': (137.5, 74.5, 90, F), 'C39': (138.0, 76.5, 90, B),
    'C49': (128.5, 70.5, 0, F), 'TP18': (131.5, 67.5, 0, F),
    'TP11': (141.0, 80.0, 0, F), 'C11': (139.5, 83.0, -90, B), 'R12': (140.5, 86.0, 180, B), 'R8': (138.0, 86.0, 180, F),
    'U3': (138.5, 91.5, 180, F), 'C25': (137.5, 94.5, 180, B), 'R24': (135.0, 93.0, -90, B), 'R25': (134.5, 87.0, 0, F),
    'C36': (137.5, 96.5, 180, B), 'TP14': (142.5, 93.0, 0, F), 'TP6': (142.5, 89.0, 0, F),
    # --- PLL / VCO (center bottom)
    'VCO1': (111.0, 108.0, 0, B), 'C14': (106.3, 105.0, -90, B), 'C33': (106.3, 108.5, 90, B), 'C13': (105.7, 111.5, 180, B),
    'C22': (111.5, 115.5, 0, B), 'R18': (111.1, 106.0, 0, F), 'R19': (111.1, 107.5, 0, F),
    'R22': (115.6, 108.0, -90, B), 'R20': (115.6, 104.3, 90, B), 'C15': (113.5, 102.3, 0, F),
    'TP25': (119.5, 110.0, 0, F), 'TP24': (97.0, 111.0, 0, F), 'TP26': (106.5, 115.0, 0, F), 'TP14_': None,
    'C17': (106.8, 101.5, 0, F),
    # --- virtual driver + feedback comparator
    'U1': (131.4, 104.5, 0, F), 'R7': (116.8, 105.5, 0, F), 'C32': (116.8, 107.5, 0, F),
    'C7': (131.5, 101.5, 90, F), 'C8': (131.5, 104.5, 90, F), 'R10': (139.3, 104.5, 90, F), 'C9': (140.3, 109.0, -90, F),
    'U2': (127.7, 112.5, 0, B), 'C6': (128.9, 109.5, 0, B), 'R47': (131.6, 112.5, 90, B), 'R51': (128.9, 115.5, 180, B), 'C18': (124.5, 109.5, 0, B),
    'TP7': (125.0, 118.5, 0, F),
    'U10': (101.0, 112.8, 0, F), 'C10': (101.0, 116.0, 0, F),
    'U11': (92.5, 86.5, 0, F), 'C20': (92.5, 89.3, 0, F),
    # --- LDO / battery / connectors / LEDs
    'U4': (146.0, 100.0, 0, F), 'C16': (146.0, 96.5, 0, F), 'C26': (146.0, 103.5, 0, F),
    'D3': (146.0, 107.0, 0, F), 'R11': (146.0, 109.5, 0, F),
    'BT1': (183.5, 88.5, 180, F),
    'J1': (75.7, 108.0, -90, F), 'D4': (92.5, 117.5, 0, F), 'R13': (88.8, 117.5, 0, F),
    # --- GND test points
    'TP1': (138.9, 70.0, 0, F), 'TP2': (142.5, 97.0, 0, F), 'TP5': (104.9, 118.0, 0, F), 'TP9': (116.5, 120.0, 0, F),
    'TP13': (138.5, 100.0, 0, F), 'TP15': (92.0, 113.5, 0, F), 'TP16': (104.0, 124.0, 0, F), 'TP17': (93.5, 119.0, 0, F),
    'TP21': (97.5, 115.5, 0, F), 'TP27': (141.0, 103.0, 0, F), 'TP29': (133.5, 116.5, 0, F), 'TP30': (111.0, 120.5, 0, F),
    'TP33': (138.0, 106.0, 0, F), 'TP38': (126.0, 56.0, 0, F),
}
PL.pop('TP14_')
for ref, spec in PL.items():
    fp = board.FindFootprintByReference(ref)
    assert fp is not None, ref
    x, y, rot, layer = spec
    if fp.GetLayer() != layer:
        fp.Flip(fp.GetPosition(), False)
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(rot)
for fp in board.GetFootprints():
    ref = fp.Reference()
    ref.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); ref.SetTextThickness(FromMM(0.12))
    cy = fp.GetCourtyard(pcbnew.F_CrtYd if fp.GetLayer() == F else pcbnew.B_CrtYd).BBox()
    h = pcbnew.ToMM(cy.GetHeight()) if cy.GetHeight() > 0 else pcbnew.ToMM(fp.GetBoundingBox(False, False).GetHeight())
    ref.SetTextAngleDegrees(0)
    if fp.GetReference().startswith(('TP', 'H')):
        ref.SetVisible(False)
missing = [fp.GetReference() for fp in board.GetFootprints() if fp.GetReference() not in PL and not fp.GetReference().startswith(('H', 'FID'))]
assert not missing, missing


def orient_top(ref, top_net):
    """rotate a vertical 2-pad part by 180 if the pad carrying top_net is not the upper one"""
    fp = board.FindFootprintByReference(ref)
    pads = sorted(fp.Pads(), key=lambda p: p.GetPosition().y)
    if pads[0].GetNetname() != top_net:
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
    assert sorted(fp.Pads(), key=lambda p: p.GetPosition().y)[0].GetNetname() == top_net, (ref, top_net)


orient_top('C58', 'Net-(ReceiverCoil1-Pin_2)')
orient_top('C1', 'Net-(C1-Pad1)')
orient_top('C47', 'Is-')
orient_top('C9', 'FB')
orient_top('D2', 'Net-(D2-K)')
for ref in ('C28', 'C29', 'C30', 'C54'):
    orient_top(ref, 'Out+')
def _bbox(fp, m=0.0):
    bb = fp.GetBoundingBox(False, False)
    return (pcbnew.ToMM(bb.GetLeft()) - m, pcbnew.ToMM(bb.GetTop()) - m, pcbnew.ToMM(bb.GetRight()) + m, pcbnew.ToMM(bb.GetBottom()) + m)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


KEEP_RECTS = [(88.7, 74.0, 94.3, 84.0), (119.5, 77.0, 122.5, 86.0),   # 5 mm C1->S1 and 2.5 mm C47->S2 tank tracks
              (98.0, 82.5, 102.6, 99.5), (117.4, 85.3, 122.0, 99.5), (102.9, 79.5, 117.1, 90.0), (102, 79.5, 118, 82.0), BUS, TANK,
              (102.6, 90.2, 117.4, 101.0),      # low-side GND island (fixed GND via array)
              (118.9, 83.6, 120.3, 85.0)]        # G2 gate via


PENDING = set()


def _blocks(f, layer, bb):
    """does footprint f keep a part with bbox bb off `layer`? same-layer parts: whole body; THT parts seen from the far side: pads only"""
    tht = any(q.GetAttribute() != pcbnew.PAD_ATTRIB_SMD for q in f.Pads())
    if f.GetLayer() == layer:
        return _overlap(bb, _bbox(f, 0.0))
    if not tht:
        return False
    for q in f.Pads():
        r = q.GetBoundingBox(); pb = (pcbnew.ToMM(r.GetLeft()) - 0.3, pcbnew.ToMM(r.GetTop()) - 0.3, pcbnew.ToMM(r.GetRight()) + 0.3, pcbnew.ToMM(r.GetBottom()) + 0.3)
        if _overlap(bb, pb):
            return True
    return False


def place_near(cap, ic, pin, netname, dists=(2.1, 2.7, 3.3, 3.9, 4.5, 5.2), layer=None, order=('out', 'perp+', 'perp-', 'in')):
    """put a 2-pad cap next to IC pin `pin`, on the IC's layer (fallback: other layer), axis pointing at the pin, supply pad nearest the pin"""
    icfp = board.FindFootprintByReference(ic)
    layer = layer if layer is not None else icfp.GetLayer()
    if _place_near(cap, ic, pin, netname, dists, layer, order):
        return True
    if _place_near(cap, ic, pin, netname, dists + (6.0, 7.0), B if layer == F else F, order):
        print('  place_near:', cap, 'placed on the other layer')
        return True
    print('  place_near: no spot for', cap, 'near', ic, pin)
    return False


def _place_near(cap, ic, pin, netname, dists, layer, order):
    icfp = board.FindFootprintByReference(ic); capfp = board.FindFootprintByReference(cap)
    pos0, rot0, lay0 = capfp.GetPosition(), capfp.GetOrientationDegrees(), capfp.GetLayer()
    px, py = pad_xy(ic, pin)
    icx, icy = pcbnew.ToMM(icfp.GetPosition().x), pcbnew.ToMM(icfp.GetPosition().y)
    ox, oy = px - icx, py - icy
    ux, uy = ((1.0 if ox > 0 else -1.0), 0.0) if abs(ox) >= abs(oy) else (0.0, (1.0 if oy > 0 else -1.0))
    r2 = math.sqrt(0.5)
    dirs = {'out': (ux, uy), 'perp+': (-uy, ux), 'perp-': (uy, -ux), 'in': (-ux, -uy),
            'd1': ((ux - uy) * r2, (uy + ux) * r2), 'd2': ((ux + uy) * r2, (uy - ux) * r2)}
    order = tuple(order) + ('d1', 'd2')
    if capfp.GetLayer() != layer:
        capfp.Flip(capfp.GetPosition(), False)
    others = [f for f in board.GetFootprints() if f.GetReference() != cap and f.GetReference() not in PENDING
              and not f.GetReference().startswith('TP')]      # test points are moved out of the way afterwards
    for d in dists:
        for k in order:
            dx, dy = dirs[k]
            x, y = px + dx * d, py + dy * d
            rot = (0 if abs(dx) >= abs(dy) else 90) if k not in ('d1', 'd2') else (math.degrees(math.atan2(-dy, dx)) % 180)
            capfp.SetPosition(P(x, y)); capfp.SetOrientationDegrees(rot)
            # supply pad toward the pin
            pads = sorted(capfp.Pads(), key=lambda q: math.hypot(pcbnew.ToMM(q.GetPosition().x) - px, pcbnew.ToMM(q.GetPosition().y) - py))
            if pads[0].GetNetname() != netname:
                capfp.SetOrientationDegrees(rot + 180)
            bb = _bbox(capfp, 0.3)
            if not (83.0 < bb[0] and bb[2] < 156.0 and 50.0 < bb[1] and bb[3] < BOARD['y1'] - 1.5):
                continue
            if any(_overlap(bb, r) for r in KEEP_RECTS):
                continue
            clash = any(_blocks(f, layer, bb) for f in others)
            if not clash:
                return True
    if capfp.GetLayer() != lay0:
        capfp.Flip(capfp.GetPosition(), False)
    capfp.SetPosition(pos0); capfp.SetOrientationDegrees(rot0)
    return False


def pad_xy(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            v = p.GetPosition(); return (pcbnew.ToMM(v.x), pcbnew.ToMM(v.y))
    raise KeyError((ref, num))


def pad_by_net(ref, netname):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNetname() == netname:
            v = p.GetPosition(); return (pcbnew.ToMM(v.x), pcbnew.ToMM(v.y))
    raise KeyError((ref, netname))

# decoupling / bootstrap caps: re-placed against their IC supply pins (loop area first, placement table second)
DECAP = [('C17', 'VCO1', '16', '5V'), ('C18', 'U2', '5', '5V'), ('C6', 'U2', '4', '2.5Vb'),
         ('C36', 'U3', '5', '5V'), ('C25', 'U3', '4', '2.5Va'),
         ('C48', 'IC3', '7', '5V'), ('C49', 'IC3', '4', '-5V'), ('C12', 'IC3', '7', '5V'),
         ('C38', 'IC2', '4', '5V'), ('C39', 'IC2', '1', '-5V'),
         ('C7', 'U1', '16', '5V'), ('C8', 'U1', '11', '5V'), ('C32', 'U1', '6', 'Net-(U1-DT)'),
         ('C26', 'U4', '1', '5V'), ('C16', 'U4', '6', 'Net-(U4-EN)'),
         ('C20', 'U11', '5', '5V'), ('C10', 'U10', '5', '5V'),
         ('C61', 'S1_Gate_Driver1', '11', '5V', F), ('C52', 'S1_Gate_Driver1', '3', '5V', F), 
         ('C24', 'S1_Gate_Driver1', '6', 'Net-(S1_Gate_Driver1-DT)', F),
         ('C62', 'U9', '11', '5V', F), ('C53', 'U9', '3', '5V', F),  ('C31', 'U9', '6', 'Net-(U9-DT)', F)]
def _clear(capfp, layer, cap):
    bb = _bbox(capfp, 0.3)
    if not (83.0 < bb[0] and bb[2] < 156.0 and 50.0 < bb[1] and bb[3] < BOARD['y1'] - 1.5):
        return False
    if any(_overlap(bb, r) for r in KEEP_RECTS):
        return False
    for f in board.GetFootprints():
        if f.GetReference() == cap or f.GetReference() in PENDING or f.GetReference().startswith('TP'):
            continue
        if _blocks(f, layer, bb):
            return False
    return True


def place_between(cap, ic, pinA, netA, pinB, netB, offs=(1.9, 2.5, 3.1, 3.7), layers=None):
    """cap parallel to the pin row, centred between pins A and B, `off` outside the row; pad of netA toward pin A"""
    icfp = board.FindFootprintByReference(ic); capfp = board.FindFootprintByReference(cap)
    ax, ay = pad_xy(ic, pinA); bx, by = pad_xy(ic, pinB)
    icx, icy = pcbnew.ToMM(icfp.GetPosition().x), pcbnew.ToMM(icfp.GetPosition().y)
    mx, my = (ax + bx) / 2, (ay + by) / 2
    horiz = abs(ax - bx) >= abs(ay - by)
    nx, ny = (0.0, (1.0 if my > icy else -1.0)) if horiz else ((1.0 if mx > icx else -1.0), 0.0)
    for layer in (layers or (icfp.GetLayer(), B if icfp.GetLayer() == F else F)):
        if capfp.GetLayer() != layer:
            capfp.Flip(capfp.GetPosition(), False)
        for off in offs:
            capfp.SetPosition(P(mx + nx * off, my + ny * off)); capfp.SetOrientationDegrees(0 if horiz else 90)
            pa = [q for q in capfp.Pads() if q.GetNetname() == netA][0]
            qx, qy = pcbnew.ToMM(pa.GetPosition().x), pcbnew.ToMM(pa.GetPosition().y)
            if math.hypot(qx - ax, qy - ay) > math.hypot(qx - bx, qy - by):      # netA pad must be the one nearer pin A
                capfp.SetOrientationDegrees(capfp.GetOrientationDegrees() + 180)
            if _clear(capfp, layer, cap):
                return True
    print('  place_between: no spot for', cap, 'near', ic, pinA, pinB)
    return False


PENDING.update(r[0] for r in DECAP)
PENDING.update(('C21', 'C23'))
for row in DECAP:
    PENDING.discard(row[0])
    place_near(*row[:4], layer=(row[4] if len(row) > 4 else None))
PENDING.discard('C21'); place_between('C21', 'S1_Gate_Driver1', '16', 'Net-(D1-K)', '14', 'S1')
PENDING.discard('C23'); place_between('C23', 'U9', '16', 'Net-(D2-K)', '14', 'S2')


def fix_tp_overlaps():
    """test points that now collide with a placed part are nudged to the nearest free spot"""
    fps = list(board.GetFootprints())
    for tp in fps:
        if not tp.GetReference().startswith('TP') or list(tp.Pads())[0].GetNetname() == 'GND':
            continue
        def clash_at(x, y):
            tp.SetPosition(P(x, y)); bb = _bbox(tp, 0.3)
            if any(_overlap(bb, r) for r in KEEP_RECTS) or not (83.0 < bb[0] and bb[2] < 150.0 and 50.0 < bb[1] and bb[3] < BOARD['y1'] - 1.5):
                return True
            lays = (F, B) if any(q.GetAttribute() != pcbnew.PAD_ATTRIB_SMD for q in tp.Pads()) else (tp.GetLayer(),)
            return any(_blocks(f, l, bb) for f in fps if f is not tp for l in lays)
        x0, y0 = pcbnew.ToMM(tp.GetPosition().x), pcbnew.ToMM(tp.GetPosition().y)
        if not clash_at(x0, y0):
            continue
        done = False
        for r in (1.5, 2.5, 3.5, 4.5, 6.0, 7.5, 9.0, 11.0):
            for k in range(16):
                a = math.pi / 8 * k
                if not clash_at(x0 + r * math.cos(a), y0 + r * math.sin(a)):
                    done = True; break
            if done:
                break
        if not done:
            tp.SetPosition(P(x0, y0)); print('  fix_tp_overlaps: could not clear', tp.GetReference())


fix_tp_overlaps()


def pair_testpoints(pitch=3.2):
    """every signal test point gets a GND test point `pitch` away (probe ground); one GND TP may serve two signals"""
    tps = [f for f in board.GetFootprints() if f.GetReference().startswith('TP')]
    netof = lambda f: list(f.Pads())[0].GetNetname()
    gnd = [f for f in tps if netof(f) == 'GND']
    sig = [f for f in tps if netof(f) != 'GND']
    pos = lambda f: (pcbnew.ToMM(f.GetPosition().x), pcbnew.ToMM(f.GetPosition().y))
    home = {g.GetReference(): g.GetPosition() for g in gnd}
    FIXED_GND = {'TP1': (122.6, 102.3),       # shared by TP22 (S2) and TP37 (G4) below the bridge
                 'TP17': (128.0, 88.0)}       # G2 test point TP35 (4.3 mm; boxed in by R40 / C4 / U9)
    for i, g in enumerate(gnd):
        if g.GetReference() in FIXED_GND:
            g.SetPosition(P(*FIXED_GND[g.GetReference()]))
        else:
            g.SetPosition(P(300.0 + 5.0 * i, 100.0))         # parked: must not block spots while pairing
    FIRST = ['TP22', 'TP19', 'TP37', 'TP35', 'TP34', 'TP36', 'TP24', 'TP26']
    sig.sort(key=lambda f: (FIRST.index(f.GetReference()) if f.GetReference() in FIRST else 99, f.GetReference()))

    def free(tp, x, y, ignore=()):
        tp.SetPosition(P(x, y)); bb = _bbox(tp, 0.3)
        if any(_overlap(bb, r) for r in KEEP_RECTS) or not (83.0 < bb[0] and bb[2] < 150.0 and 50.0 < bb[1] and bb[3] < BOARD['y1'] - 1.5):
            return False
        skip = {tp.GetReference()} | {g.GetReference() for g in ignore}
        return not any(_blocks(f, l, bb) for f in board.GetFootprints() if f.GetReference() not in skip for l in (F, B))
    DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071), (0.7071, -0.7071), (-0.7071, -0.7071)]
    DIRS += [(math.cos(math.pi / 8 * k), math.sin(math.pi / 8 * k)) for k in range(1, 16, 2)]
    pairs = {}; used = [g for g in gnd if g.GetReference() in FIXED_GND]
    for g in used:
        if not free(g, *FIXED_GND[g.GetReference()]):
            print('  pair_testpoints: fixed GND test point spot is NOT free:', g.GetReference())

    def try_partner(s_):
        sx, sy = pos(s_)
        for g in sorted((g for g in gnd if g not in used), key=lambda g: math.hypot(pos(g)[0] - sx, pos(g)[1] - sy))[:4]:
            g0 = g.GetPosition()
            for d in (pitch, pitch * 1.2, pitch * 1.4, pitch * 1.7, pitch * 2.0):
                for dx, dy in DIRS:
                    if free(g, sx + dx * d, sy + dy * d, ignore=(s_,)):
                        used.append(g); return g.GetReference(), round(d, 2)
            g.SetPosition(g0)
        return None

    for s_ in sig:
        s0 = s_.GetPosition(); sx0, sy0 = pos(s_); got = None
        near = [(math.hypot(pos(g)[0] - sx0, pos(g)[1] - sy0), g.GetReference()) for g in used if g.GetReference() in FIXED_GND]
        if near and min(near)[0] <= 4.4:
            pairs[s_.GetReference()] = (min(near)[1] + ' (fixed)', round(min(near)[0], 2)); continue
        # keep the signal TP where it is if a ground partner fits; otherwise move it a little (it stays near its net)
        for rs in (0.0, 2.0, 3.5, 5.0, 7.0):
            for ddx, ddy in ([(0, 0)] if rs == 0 else DIRS):
                if rs and not free(s_, sx0 + ddx * rs, sy0 + ddy * rs):
                    continue
                s_.SetPosition(P(sx0 + ddx * rs, sy0 + ddy * rs))
                got = try_partner(s_)
                if got:
                    break
            if got:
                break
        if got:
            pairs[s_.GetReference()] = got
            continue
        s_.SetPosition(s0)
        # no free ground TP: share the nearest already placed one if the signal TP can sit on its far side
        for g in sorted(used, key=lambda g: math.hypot(pos(g)[0] - sx0, pos(g)[1] - sy0)):
            gx, gy = pos(g); done = False
            for dx, dy in DIRS:
                if free(s_, gx + dx * pitch, gy + dy * pitch, ignore=(g,)):
                    done = True; break
            if done:
                pairs[s_.GetReference()] = (g.GetReference() + ' (shared)', pitch); break
            s_.SetPosition(s0)
        else:
            print('  pair_testpoints: no ground partner for', s_.GetReference())
    for k, v in sorted(pairs.items()):
        print(f'  TP pair {k:5} <-> {v[0]:14} {v[1]} mm')
    for g in gnd:
        if g in used:
            continue
        x0, y0 = pcbnew.ToMM(home[g.GetReference()].x), pcbnew.ToMM(home[g.GetReference()].y)
        ok = free(g, x0, y0)
        for r in (0, 1.5, 2.5, 3.5, 4.5, 6.0, 8.0):
            if ok:
                break
            for k in range(16):
                a = math.pi / 8 * k
                if free(g, x0 + r * math.cos(a), y0 + r * math.sin(a)):
                    ok = True; break
        if not ok:
            g.SetPosition(home[g.GetReference()]); print('  pair_testpoints: spare GND test point could not be placed', g.GetReference())
        else:
            print('  pair_testpoints: spare GND test point', g.GetReference(), 'at', pos(g))


pair_testpoints()


def fix_footprints():
    """same repairs as in libs/: IC2 courtyard centre-cross -> F.Fab, U4 thermal pad 1.0 mm wide; hide every silkscreen
    text that is not the reference (vendor footprints carry 'Designator..' / '*' texts that collide with everything)"""
    ic2 = board.FindFootprintByReference('IC2')
    for g in list(ic2.GraphicalItems()):
        if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd) and g.GetClass() == 'PCB_SHAPE' and pcbnew.ToMM(g.GetLength()) < 1.2:
            g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_CrtYd else pcbnew.B_Fab)
    for q in board.FindFootprintByReference('U4').Pads():
        if q.GetNumber() == '7':
            q.SetSize(pcbnew.VECTOR2I(FromMM(1.0), q.GetSize().y))
    n = 0
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetClass() == 'PCB_TEXT' and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                txt = g.GetText()
                if txt.strip() == '*' or txt.startswith('Designator'):       # vendor pin-1 stars / designator placeholders -> Fab layer
                    g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab); n += 1
    print('  fix_footprints: removed/hid', n, 'stray silkscreen texts')


fix_footprints()
# flying cap of the charge pump: centred between its two pins, just outside the package
p5, p6 = pad_xy('IC2', '5'), pad_xy('IC2', '6')
icc = board.FindFootprintByReference('IC2').GetPosition()
mx, my = (p5[0] + p6[0]) / 2, (p5[1] + p6[1]) / 2
vx, vy = mx - pcbnew.ToMM(icc.x), my - pcbnew.ToMM(icc.y); vn = math.hypot(vx, vy)
c40 = board.FindFootprintByReference('C40')
c40.SetPosition(P(mx + vx / vn * 1.9, my + vy / vn * 1.9)); c40.SetOrientationDegrees(90 if abs(p5[0] - p6[0]) < abs(p5[1] - p6[1]) else 0)
if math.hypot(pad_xy('C40', '1')[0] - p5[0], pad_xy('C40', '1')[1] - p5[1]) > math.hypot(pad_xy('C40', '2')[0] - p5[0], pad_xy('C40', '2')[1] - p5[1]):
    c40.SetOrientationDegrees(c40.GetOrientationDegrees() + 180)


# ---------------------------------------------------------------- 4) zones
ZONES = []


def zone(netname, layers, pts, prio, solid=False, clearance=0.2):
    z = pcbnew.ZONE(board); z.SetNet(net(netname))
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(x), FromMM(y))
    z.SetMinThickness(FromMM(0.25)); z.SetThermalReliefGap(FromMM(0.3)); z.SetThermalReliefSpokeWidth(FromMM(0.4))
    z.SetLocalClearance(FromMM(clearance))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetAssignedPriority(prio); z.SetZoneName(netname)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA); z.SetMinIslandArea(int(2.0 * 1e12))
    board.Add(z); ZONES.append((netname, layers, pts)); return z


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def keepout(pts, layers):
    z = pcbnew.ZONE(board); z.SetIsRuleArea(True)
    z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(x), FromMM(y))
    board.Add(z)


bx0, by0, bx1, by1 = BOARD['x0'], BOARD['y0'], BOARD['x1'], BOARD['y1']
# main ground on all four layers
PWR_BLOCK = (87.0, 73.9, 124.0, 100.0)
zone('GND', CU4, [(bx0, by0), (87.0, by0), (87.0, 100.0), (124.0, 100.0), (124.0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], 0, clearance=0.15)
zone('GND', (F, B, IN2), rect(86.9, 83.0, 98.0, 101.0), 1, clearance=0.15)   # S1 driver area (In1 is 5V here)
zone('GND', CU4, rect(102.6, 90.2, 117.4, 101.0), 1, clearance=0.15)        # low-side sources + decoupling caps
keepout(rect(*TANK), CU4)
# 5V plane island on In1 under the control / sense / LDO areas
FIVEV = [(87.5, 83.5), (97.5, 83.5), (97.5, 100.0), (126, 100), (126, 68), (150, 68), (150, 122), (87.5, 122)]
zone('5V', (IN1,), FIVEV, 1)
# switch-node islands (all layers) -- thermal copper for the FETs
S1R = (98.0, 82.5, 102.6, 99.5)
S2R = (117.4, 85.3, 122.0, 99.5)
S1POLY = [(98.0, 82.5), (102.6, 82.5), (102.6, 87.6), (101.0, 87.6), (101.0, 93.4), (102.6, 93.4), (102.6, 99.5), (98.0, 99.5)]
zone('S1', CU4, S1POLY, 3, solid=True)
zone('S2', CU4, rect(*S2R), 3, solid=True)
# Out+ : band above the bridge + middle column, neck to the bulk caps (inner/bottom only) and the left bus to the XT60
OUTR = (105.5, 79.5, 114.5, 90.0)  # overlaps the Q1/Q3 drain bar ends (105.7 / 114.3) so the pour connects
zone('Out+', CU4, [(102.0, 79.5), (118.0, 79.5), (118.0, 82.0), (114.5, 82.0), (114.5, 90.0), (105.5, 90.0), (105.5, 82.0), (102.0, 82.0)], 3, solid=True)
OUTB = (102.9, 82.0, 117.1, 90.0)
zone('Out+', (B, IN1, IN2), rect(*OUTB), 2, solid=True)   # under both FET columns: C28/C29 and C30/C54 Out+ pads land here
for fp_ in board.GetFootprints():
    if len(fp_.Pads()) > 3:
        for p_ in fp_.Pads():
            if p_.GetNetname() == 'GND':
                p_.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
# FET pads and the power caps get solid (no thermal relief) zone connections
for ref in ('Q1', 'Q2', 'Q3', 'Q4', 'C19', 'C27', 'C28', 'C29', 'C30', 'C54', 'J1', 'C47', 'C1', 'C58', 'C31'):   # C31: at the pour notch edge, only one thermal spoke fits
    for p in board.FindFootprintByReference(ref).Pads():
        p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
zone('Out+', (B, IN1), rect(83.0, 77.5, 106.0, 82.0), 4, solid=True)
zone('Out+', (F, B, IN1), rect(*BUS), 2, solid=True)
# the sense cap node and the C58/C1 link get small pours like the sample

# ---------------------------------------------------------------- 5) vias (thermal arrays + stitching)
VIAS = []


def via(x, y, netname, size=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetDrill(FromMM(drill)); v.SetWidth(FromMM(size))
    v.SetLayerPair(F, B); v.SetNet(net(netname)); board.Add(v); VIAS.append((x, y, netname, size))


def frange(a, b, s):
    v = a
    while v <= b + 1e-6:
        yield round(v, 3); v += s


for x in frange(99.0, 101.0, 2.0):
    for y in frange(83.5, 98.5, 2.0):
        if x > 100.9 and 87.6 - 0.5 < y < 93.4 + 0.5:
            continue
        via(x, y, 'S1')
for x in frange(118.5, 120.5, 2.0):
    for y in frange(86.5, 98.5, 2.0):
        via(x, y, 'S2')
for x in frange(108.3, 112.5, 1.4):
    for y in frange(82.5, 89.0, 1.6):
        via(x, y, 'Out+')
for x in (103.3, 105.0, 115.0, 116.7):
    via(x, 80.8, 'Out+')
for x, y in ((84.0, 84.5), (85.5, 84.5), (84.0, 110.0), (85.5, 110.0)):   # tie the Out+ bus layers at the neck and mid-way; the THT caps / XT60 do the rest
    via(x, y, 'Out+')
for x in frange(107.9, 112.3, 1.1):
    for y in (95.2, 96.7, 98.2):
        via(x, y, 'GND')
via(116.4, 99.0, 'GND')
# ---------------------------------------------------------------- 6) explicit power tracks
TRACKS = []


def track(a, b, netname, w, layer):
    t = pcbnew.PCB_TRACK(board); t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(FromMM(w)); t.SetLayer(layer)
    t.SetNet(net(netname)); board.Add(t); TRACKS.append((a, b, netname, w, layer))


def poly(pts, netname, w, layer):
    for a, b in zip(pts, pts[1:]):
        track(a, b, netname, w, layer)


# resonant tank: coil -> C58 -> C1 -> S1 island ; coil(Is-) -> C47 -> S2 island
coil2 = pad_by_net('ReceiverCoil1', 'Net-(ReceiverCoil1-Pin_2)'); coil1 = pad_by_net('ReceiverCoil1', 'Is-')
c58a = pad_by_net('C58', 'Net-(ReceiverCoil1-Pin_2)'); c58b = pad_by_net('C58', 'Net-(C1-Pad1)')
c1a = pad_by_net('C1', 'Net-(C1-Pad1)'); c1b = pad_by_net('C1', 'S1')
c47a = pad_by_net('C47', 'Is-'); c47b = pad_by_net('C47', 'S2')
def fat(pts, netname, w, both=True, stitch=(), pad_ends=(True, True), link_w=1.2, back=2.0):
    """wide copper path; where an end is a component pad the wide part stops `back` mm short and a pad-width link finishes"""
    pts = list(pts)
    links = []
    for end, idx, nxt in ((pad_ends[0], 0, 1), (pad_ends[1], -1, -2)):
        if not end:
            continue
        p, q = pts[idx], pts[nxt]
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        assert d > back + 0.1, (netname, p, q)
        m = (p[0] + (q[0] - p[0]) * back / d, p[1] + (q[1] - p[1]) * back / d)
        links.append((p, m)); pts[idx] = m
    for layer in ((F, B) if both else (F,)):
        poly(pts, netname, w, layer)
        if layer == F:                      # pads are on the front; the back copy ends at the stitching vias
            for p, m in links:
                poly([p, m], netname, link_w, layer)
    for x, y in stitch:
        via(x, y, netname)


fat([coil2, (coil2[0], 60.5), (c58a[0], 60.5), c58a], 'Net-(ReceiverCoil1-Pin_2)', 5.0, pad_ends=(False, True),
    stitch=[(coil2[0] - 1.1, 62.0), (coil2[0] + 1.1, 62.0), (97.0, 59.2), (97.0, 61.8), (c58a[0] - 1.1, 62.0), (c58a[0] + 1.1, 62.0)])
fat([c58b, c1a], 'Net-(C1-Pad1)', 5.0, back=1.4, stitch=[(c58b[0] - 1.3, (c58b[1] + c1a[1]) / 2), (c58b[0] + 1.3, (c58b[1] + c1a[1]) / 2)])
fat([c1b, (c1b[0], 80.0), (99.0, 80.0), (99.0, 83.0)], 'S1', 5.0, both=False, pad_ends=(True, False))   # back side is the Out+ neck here
fat([coil1, (c47a[0], coil1[1]), (c47a[0], c47a[1] - 2.0)], 'Is-', 5.0, pad_ends=(False, False),
    stitch=[(119.6, coil1[1] - 1.0), (119.6, coil1[1] + 1.0)])
poly([(c47a[0], c47a[1] - 2.0), c47a], 'Is-', 1.2, F)
fat([c47b, (c47b[0] + 0.5, 79.0), (c47b[0] + 0.5, 86.0)], 'S2', 2.5, pad_ends=(True, False), back=1.2, link_w=1.2,
    stitch=[(c47b[0] + 0.5, 80.0), (c47b[0] + 0.5, 82.0)])

# bulk caps and XT60 on the Out+ bus / GND
for ref in ('C19', 'C27'):
    o = pad_by_net(ref, 'Out+'); poly([o, (85.0, o[1])], 'Out+', 2.0, F)
j1o = pad_by_net('J1', 'Out+'); poly([j1o, (85.0, j1o[1])], 'Out+', 2.5, F)
poly([pad_xy('U4', 5), pad_xy('U4', 7)], 'GND', 0.25, F)
r13 = pad_by_net('R13', 'Out+'); poly([r13, (85.5, r13[1])], 'Out+', 0.5, F)
# gate escapes: each gate leaves the FET through the row gap / outside the copper islands, then drops to B.Cu
GATES = {
    'Q3': ('G2', [(119.6, 84.325)]),                                   # top-right gate (rot 180) -> right, above S2 island
    'Q4': ('G4', [(113.0, 97.675)]),                                   # bottom-left gate -> left, middle column
}
for q, (netname, pts) in GATES.items():
    g = pad_xy(q, 1)
    assert abs(g[1] - pts[0][1]) < 0.01 or abs(g[0] - pts[0][0]) < 0.01, (q, g, pts[0])
    poly([g] + pts, netname, 0.3, F)
    via(*pts[-1], netname, 0.6, 0.3)
# bootstrap caps of the two Si8274 drivers: straight stubs from the cap pads to VDDA (16) / VSSA (14) on B.Cu
for cap, ic in (('C21', 'S1_Gate_Driver1'), ('C23', 'U9')):
    for pin in ('16',):      # VSSA side (pin 14) is left to the router so it also gets tied into the S1/S2 island
        pn = [q for q in board.FindFootprintByReference(ic).Pads() if q.GetNumber() == pin][0].GetNetname()
        cp = pad_by_net(cap, pn); ip = pad_xy(ic, pin)
        mid_y = cp[1] + (0.5 if ip[1] > cp[1] else -0.5)
        poly([cp, (ip[0], mid_y), ip], pn, 0.3, B)
# G1 / G3: hand-routed (the lane between the S1 island and the bridge caps is too tight for the grid router)
g1 = pad_xy('Q1', 1)
poly([g1, (101.6, g1[1])], 'G1', 0.3, F); via(101.6, g1[1], 'G1', 0.6, 0.3)   # left into the S1 island notch, down to B.Cu
poly([(101.6, g1[1]), (101.6, 91.0), (103.3, 91.0), (103.3, 100.1), (97.5, 100.1), pad_xy('R41', 2)], 'G1', 0.3, B)
#   ^ out of the notch, down the lane between the S1 island and C28 (no sealed GND pocket), then to R41
g3 = pad_xy('Q2', 1)
poly([g3, (107.1, g3[1]), (107.1, 101.6)], 'G3', 0.3, F); via(107.1, 101.6, 'G3', 0.6, 0.3)   # right of Q2 on F.Cu, down past the GND via array
poly([(107.1, 101.6), (97.5, 101.6), pad_xy('R42', 2)], 'G3', 0.3, B)
# U9 pin 11 (5V) gets its In1 via explicitly (TP17 / R40 crowd its surroundings)
poly([pad_xy('U9', 11), (126.79, 89.3)], '5V', 0.3, B); via(126.79, 89.3, '5V', 0.6, 0.3)
C47W = 1.6
# Q1 source pads (bottom row) -> S1 island through the notch; Q3 source pads (top row) -> S2 island
poly([pad_xy('Q1', 14), (pad_xy('Q1', 14)[0], 89.9), (100.6, 89.9)], 'S1', 1.0, F)
poly([pad_xy('Q3', 14), (pad_xy('Q3', 14)[0], 83.2), (120.4, 83.2), (120.4, 85.7)], 'S2', 0.6, F)
# every EPC2305 bar gets a finger into its copper island (the 0.2-0.3 mm overlap alone is below the pour's min width)
for q, nums, dx in (('Q1', (3, 5, 7), +1), ('Q1', (4, 6), -1), ('Q2', (3, 5, 7), -1), ('Q2', (4, 6), +1),
                    ('Q3', (3, 5, 7), -1), ('Q3', (4, 6), +1), ('Q4', (3, 5, 7), +1), ('Q4', (4, 6), -1)):
    for n in nums:
        fp = board.FindFootprintByReference(q)
        pad = [pp for pp in fp.Pads() if pp.GetNumber() == str(n)][0]
        bb = pad.GetBoundingBox(); yb = pcbnew.ToMM(pad.GetPosition().y)
        xe = pcbnew.ToMM(bb.GetRight()) if dx > 0 else pcbnew.ToMM(bb.GetLeft())
        poly([(xe - 0.15 * dx, yb), (xe + 0.75 * dx, yb)], pad.GetNetname(), 0.3, F)
# drain pad rows -> drain copper
poly([pad_xy('Q1', 8), (105.9, pad_xy('Q1', 8)[1])], 'Out+', 0.3, F)
poly([pad_xy('Q3', 8), (114.1, pad_xy('Q3', 8)[1])], 'Out+', 0.3, F)
poly([pad_xy('Q2', 8), (102.2, pad_xy('Q2', 8)[1])], 'S1', 0.3, F)
poly([pad_xy('Q4', 8), (117.8, pad_xy('Q4', 8)[1])], 'S2', 0.3, F)

# ---------------------------------------------------------------- 7) GND stitching grid (skip anything close to other copper)
def all_pads():
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            v = p.GetPosition(); s = p.GetSize()
            out.append((pcbnew.ToMM(v.x), pcbnew.ToMM(v.y), max(pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)) / 2, p.GetNetname(),
                        p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD, fp.GetLayer()))
    return out


PADS = all_pads()


def seg_dist(x, y, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def inside(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


NOGO = [S1R, S2R, (102, 79.5, 118, 90.3), BUS, TANK, (151.0, 56.0, 213.0, 121.0), (95.0, 99.5, 124.0, 102.0), (83.0, 77.0, 106.0, 82.5)]
# a GND via next to each gate driver's GNDI/GNDB pin (pour connection between pin rows is marginal); checked for clearance
for ref_, pins_ in (('S1_Gate_Driver1', ('4', '9')), ('U9', ('4', '9'))):
    fp_ = board.FindFootprintByReference(ref_)
    cy_ = pcbnew.ToMM(fp_.GetPosition().y)
    for p_ in fp_.Pads():
        if p_.GetNumber() not in pins_:
            continue
        c_ = p_.GetPosition(); px_, py_ = pcbnew.ToMM(c_.x), pcbnew.ToMM(c_.y)
        sgn = 1 if py_ > cy_ else -1
        for dx_, dy_ in ((0, 1.95), (0.5, 1.95), (-0.5, 1.95), (0, 2.5), (0.6, 2.5), (-0.6, 2.5), (0, 3.0)):
            x_, y_ = px_ + dx_, py_ + sgn * dy_
            if any(math.hypot(x_ - qx, y_ - qy) < qr + 0.3 + 0.25 for qx, qy, qr, qn, qt, ql in PADS if qn != 'GND'):
                continue
            if any(math.hypot(x_ - vx, y_ - vy) < 0.9 for vx, vy, vn, vs in VIAS):
                continue
            if any(seg_dist(x_, y_, a, b) < w / 2 + 0.3 + 0.25 for a, b, n_, w, l_ in TRACKS):
                continue
            via(x_, y_, 'GND'); break
        else:
            print('  no safe GND via spot for', ref_, p_.GetNumber())

STITCH = [(87.5, 84.0, 97.5, 88.5),      # S1 driver GND island (ties its F/B/In2 layers)
          (88.0, 101.5, 124.0, 103.5),    # strip just below the power block
          (124.5, 84.0, 126.5, 100.0)]    # strip right of the S2 island
for x in frange(76.0, 148.0, 2.5):
    for y in frange(60.0, 140.0, 2.5):
        if not any(inside(x, y, r) for r in STITCH) or any(inside(x, y, r) for r in NOGO):
            continue
        if any(math.hypot(x - px, y - py) < pr + 1.0 for px, py, pr, pn, tht, ly in PADS if pn != 'GND'):
            continue
        if any(math.hypot(x - px, y - py) < pr + 0.9 for px, py, pr, pn, tht, ly in PADS if pn == 'GND'):
            continue
        if any(math.hypot(x - hx, y - hy) < 3.5 for hx, hy in HOLES):
            continue
        if any(math.hypot(x - vx, y - vy) < 1.2 for vx, vy, vn, vs in VIAS):
            continue
        if any(seg_dist(x, y, a, b) < w / 2 + 0.3 + 0.3 for a, b, n_, w, l_ in TRACKS):
            continue
        via(x, y, 'GND')

# ---------------------------------------------------------------- 8) signal routing
if ROUTE:
    sys.path.insert(0, r'C:\Users\Vedant\AppData\Local\Temp\claude\C--Users-Vedant-Documents-KiCad-Guad-Rectifier\f8062ecd-e151-4ec2-ab6b-2615ce91d466\scratchpad\work\pcb')
    import router
    unrouted = router.route_all(board, nogo=[((98.0, 82.5, 101.0, 99.5), CU4, 'S1'), ((101.0, 82.5, 102.6, 87.6), CU4, 'S1'), ((101.0, 93.4, 102.6, 99.5), CU4, 'S1'), (S2R, CU4, 'S2'), (OUTR, CU4, 'Out+'), ((102, 79.5, 118, 82.0), CU4, 'Out+'),
                                  (BUS, (F, B), 'Out+'), ((83, 77.5, 106, 82), (B,), 'Out+'), (OUTB, (B,), 'Out+'), (TANK, CU4, None)],
                     fiveV_island=[FIVEV], board_rect=(bx0, by0, bx1, by1))


def chamfer_tracks(cmin=0.2, clr=0.2):
    """replace each 90-degree corner between two track segments (same layer, net, width) by a 45-degree mitre;
    a mitre is skipped when its diagonal would come closer than `clr` to copper of another net"""
    mmf = pcbnew.ToMM
    segs = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
    vias_ = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
    kp = lambda v: (round(mmf(v.x), 3), round(mmf(v.y), 3))
    ends = {}
    for t in segs:
        for v in (t.GetStart(), t.GetEnd()):
            ends.setdefault((t.GetLayer(), kp(v)), []).append(t)
    via_at = {kp(v.GetPosition()) for v in vias_}
    pads_ = []
    for f in board.GetFootprints():
        for q in f.Pads():
            bb = q.GetBoundingBox()
            pads_.append((q.GetNetCode(), (mmf(bb.GetLeft()), mmf(bb.GetTop()), mmf(bb.GetRight()), mmf(bb.GetBottom())), q.IsOnLayer(F), q.IsOnLayer(B)))

    def sdist(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def ssdist(a1, a2, b1, b2):
        d1, d2 = cross(b1, b2, a1), cross(b1, b2, a2); d3, d4 = cross(a1, a2, b1), cross(a1, a2, b2)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
            return 0.0
        return min(sdist(a1, b1, b2), sdist(a2, b1, b2), sdist(b1, a1, a2), sdist(b2, a1, a2))

    def rect_seg_dist(r, a, b):
        best = 1e9
        for k in range(9):
            t = k / 8.0; x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            dx = max(r[0] - x, 0.0, x - r[2]); dy = max(r[1] - y, 0.0, y - r[3])
            best = min(best, math.hypot(dx, dy))
        return best

    n = 0; skipped = 0
    for (layer, pt), ts in list(ends.items()):
        if len(ts) != 2 or pt in via_at:
            continue
        a, b = ts
        if a.GetNetCode() != b.GetNetCode() or a.GetWidth() != b.GetWidth():
            continue
        def other(t):
            s0, e0 = kp(t.GetStart()), kp(t.GetEnd()); return e0 if s0 == pt else s0
        oa, ob = other(a), other(b)
        da = (oa[0] - pt[0], oa[1] - pt[1]); db = (ob[0] - pt[0], ob[1] - pt[1])
        la, lb = math.hypot(*da), math.hypot(*db)
        if la < 1e-6 or lb < 1e-6 or abs(da[0] * db[0] + da[1] * db[1]) > 1e-3 * la * lb:
            continue                                                    # not a right angle
        w = mmf(a.GetWidth()); net = a.GetNetCode()
        if any(nc == net and r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3] for nc, r, _, _ in pads_):
            continue                                                    # corner inside its own pad
        cfull = min(max(0.8, w), 0.45 * la, 0.45 * lb)
        if cfull < cmin:
            continue
        need = w / 2 + clr + 0.03
        onF = (layer == F)

        def fits(c):
            A = (pt[0] + da[0] / la * c, pt[1] + da[1] / la * c); Bp = (pt[0] + db[0] / lb * c, pt[1] + db[1] / lb * c)
            for t in segs:
                if t.GetNetCode() != net and t.GetLayer() == layer and ssdist(A, Bp, kp(t.GetStart()), kp(t.GetEnd())) < need + mmf(t.GetWidth()) / 2:
                    return None
            for v in vias_:
                if v.GetNetCode() != net and sdist(kp(v.GetPosition()), A, Bp) < need + mmf(v.GetWidth(layer)) / 2:
                    return None
            for nc, r, pf, pb in pads_:
                if nc != net and ((onF and pf) or ((not onF) and pb)) and rect_seg_dist(r, A, Bp) < need:
                    return None
            r_keep = w / 2 - 0.05
            for v in vias_:
                if v.GetNetCode() != net:
                    continue
                vp = kp(v.GetPosition())
                if math.hypot(vp[0] - pt[0], vp[1] - pt[1]) > w / 2 + mmf(v.GetWidth(layer)) / 2 + 0.1:
                    continue
                if min(sdist(vp, oa, A), sdist(vp, ob, Bp), sdist(vp, A, Bp)) > r_keep + mmf(v.GetWidth(layer)) / 2:
                    return None
            return A, Bp
        got = None
        for c in (cfull, cfull * 0.6, cfull * 0.35, 0.15):
            if c < 0.15:
                break
            got = fits(c)
            if got:
                break
        if not got:
            skipped += 1; continue
        A, Bp = got
        for t, newpt in ((a, A), (b, Bp)):
            if kp(t.GetStart()) == pt:
                t.SetStart(P(*newpt))
            else:
                t.SetEnd(P(*newpt))
        d = pcbnew.PCB_TRACK(board); d.SetStart(P(*A)); d.SetEnd(P(*Bp)); d.SetWidth(a.GetWidth()); d.SetLayer(layer); d.SetNet(a.GetNet()); board.Add(d)
        n += 1
    print(f'  chamfer_tracks: mitred {n} right-angle corners, {skipped} left (clearance)')


chamfer_tracks()
# ---------------------------------------------------------------- 9) fill, stitch isolated GND pockets, place text, save
def seg_d(x, y, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def via_spot_clear(x, y):
    """can a 0.6 mm GND via go at (x, y)? keep 0.5 mm from every pad / track / via and out of the islands"""
    if any(inside(x, y, r) for r in (S1R, S2R, OUTR, OUTB, (102, 79.5, 118, 82), BUS, (83, 77.5, 106, 82), TANK)):
        return False
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            m = 0.1 if p.GetNetname() == 'GND' else 0.55
            if pcbnew.ToMM(bb.GetLeft()) - m < x < pcbnew.ToMM(bb.GetRight()) + m and pcbnew.ToMM(bb.GetTop()) - m < y < pcbnew.ToMM(bb.GetBottom()) + m:
                return False
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition()
            if math.hypot(x - pcbnew.ToMM(c.x), y - pcbnew.ToMM(c.y)) < 0.6 + 0.3:
                return False
        else:
            a, e = t.GetStart(), t.GetEnd()
            if seg_d(x, y, (pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)), (pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))) < pcbnew.ToMM(t.GetWidth()) / 2 + (0.35 if t.GetNetname() == 'GND' else 0.55):
                return False
    return True


def stitch_islands():
    """after a fill, put a GND via into every GND pour pocket (> 1 mm^2) that is cut off from the main pour"""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gz = [z for z in board.Zones() if z.GetNetname() == 'GND' and not z.GetIsRuleArea()][0]
    added = 0
    for l in gz.GetLayerSet().Seq():
        ps = gz.GetFilledPolysList(l)
        n = ps.OutlineCount()
        if n <= 1:
            continue
        order = sorted(range(n), key=lambda i: -abs(ps.Outline(i).Area()))
        for i in order[1:]:
            o = ps.Outline(i)
            if abs(o.Area()) < 1.0e12:          # < 1 mm^2 (internal units are nm)
                continue
            bb = o.BBox()
            x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()); x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
            best = None
            for gy in frange(y0 + 0.4, y1 - 0.4, 0.3):
                for gx in frange(x0 + 0.4, x1 - 0.4, 0.3):
                    if not ps.Contains(P(gx, gy), i):
                        continue
                    if via_spot_clear(gx, gy):
                        best = (gx, gy); break
                if best:
                    break
            if best:
                via(best[0], best[1], 'GND'); added += 1
            else:
                print(f'  island on {pcbnew.BOARD.GetStandardLayerName(l)} at x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}] area {abs(o.Area())/1e12:.1f} mm2: no via spot')
    print('stitch_islands: added', added, 'vias')
    return added


for _ in range(3):
    if not stitch_islands():
        break
# final fill: pad-less slivers below 6 mm^2 are dropped
for z_ in board.Zones():
    if not z_.GetIsRuleArea():
        z_.SetMinIslandArea(int(6.0 * 1e12))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def place_refs():
    """put each reference where it sits on no pad / via / silkscreen graphic / other reference (0.8 mm text)"""
    def bbmm(bb):
        return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    def overlap(a, b, m=0.12):
        return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]
    pads = {F: [], B: []}; silk = {F: [], B: []}
    for fp in board.GetFootprints():
        side = fp.GetLayer()
        for p in fp.Pads():
            r = bbmm(p.GetBoundingBox())
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                pads[side].append(r)
            else:
                pads[F].append(r); pads[B].append(r)
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS:
                silk[F].append(bbmm(g.GetBoundingBox()))
            elif g.GetLayer() == pcbnew.B_SilkS:
                silk[B].append(bbmm(g.GetBoundingBox()))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition(); x, y = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            for side in (F, B):
                pads[side].append((x - 0.35, y - 0.35, x + 0.35, y + 0.35))
    placed = {F: [], B: []}
    unplaced = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.Reference()
        if not ref.IsVisible():
            continue
        side = fp.GetLayer()
        ref.SetTextSize(pcbnew.VECTOR2I(FromMM(0.8), FromMM(0.8))); ref.SetTextThickness(FromMM(0.12))
        ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); ref.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        ref.SetTextAngleDegrees(0)
        fb = bbmm(fp.GetBoundingBox(False, False))
        cx, cy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        ref.SetPosition(P(cx, cy)); tb = bbmm(ref.GetBoundingBox()); w, h = tb[2] - tb[0], tb[3] - tb[1]
        cands = []
        for d in (0.35, 0.9, 1.6, 2.4, 3.2):
            cands += [(cx, fb[1] - d - h / 2), (cx, fb[3] + d + h / 2), (fb[0] - d - w / 2, cy), (fb[2] + d + w / 2, cy),
                      (fb[0] - d - w / 2, fb[1] - d - h / 2), (fb[2] + d + w / 2, fb[1] - d - h / 2),
                      (fb[0] - d - w / 2, fb[3] + d + h / 2), (fb[2] + d + w / 2, fb[3] + d + h / 2)]
            cands += [(cx - 1.5, fb[1] - d - h / 2), (cx + 1.5, fb[1] - d - h / 2), (cx - 1.5, fb[3] + d + h / 2), (cx + 1.5, fb[3] + d + h / 2)]
        best, bestn = None, 1e9
        for x, y in cands:
            r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            if not (bx0 + 0.6 < r[0] and r[2] < bx1 - 0.6 and by0 + 0.6 < r[1] and r[3] < by1 - 0.6):
                continue
            n = 10 * sum(1 for o in pads[side] if overlap(r, o)) + 3 * sum(1 for o in silk[side] if overlap(r, o)) \
                + 3 * sum(1 for o in placed[side] if overlap(r, o)) + 0.01 * math.hypot(x - cx, y - cy)
            if n < bestn:
                best, bestn = (x, y, r), n
            if n < 0.05:
                break
        x, y, r = best
        ref.SetPosition(P(x, y)); placed[side].append(r)
        if bestn >= 3:                                   # no clean spot: hide the designator rather than print it over other silk
            unplaced.append((fp.GetReference(), round(bestn, 1))); ref.SetVisible(False)
    print('  place_refs: references hidden (no collision-free spot):', unplaced)


place_refs()
pcbnew.SaveBoard(DST, board)
print('saved', DST, 'vias', len(VIAS), 'tracks', len(TRACKS), 'unrouted', unrouted if ROUTE else 'n/a')

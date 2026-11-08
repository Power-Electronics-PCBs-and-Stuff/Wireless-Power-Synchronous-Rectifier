"""Grid router for the signal nets (F.Cu / B.Cu, through vias) of the synchronous-rectifier board.

Masks (grid 0.2 mm, index [layer, iy, ix] unless noted):
  pocc     pad obstacles: pad bodies, escape lanes and clearance halos by net code (-1 = blocked for all)
  own      pad bodies + escape lanes by net code: a net may always travel through its own pad cells
  tocc     track / via / island obstacles by net code (-1 = blocked for all)
  via_occ  2-D map for via centres (0 free, >0 net code, -1 blocked)
  copper   exact copper cells per net code (island rects, track centrelines, vias) -> seeds for routing
A cell is free for net X when tocc in {0, X} and (pocc in {0, X} or own == X).
5V pads connect by dropping a via into the In1 5V plane island; S1 / S2 / Out+ pads route to their islands.
"""
import heapq
import math

import numpy as np
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

G = 0.2
CLR = 0.2
PAD_M = 0.38
W_DEFAULT = 0.25
W_THICK = 0.35
THICK = {'5V', '-5V', 'Net-(U4-EN)', 'S1', 'S2', 'Out+'}
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 45.0
TURN_COST = 0.4
MAX_EXPAND = 1500000
SKIP = {'GND', ''}
F, B = pcbnew.F_Cu, pcbnew.B_Cu
LAY = {F: 0, B: 1}
BLOCK = -1
X0, Y0, X1, Y1 = 64.5, 48.5, 216.5, 147.5


def halo(w):
    return w / 2 + CLR + W_THICK / 2 + 0.03


class Router:
    def __init__(self, board, nogo, island):
        self.b = board
        self.nx = int(round((X1 - X0) / G)) + 1
        self.ny = int(round((Y1 - Y0) / G)) + 1
        shape = (2, self.ny, self.nx)
        self.pocc = np.zeros(shape, dtype=np.int32)
        self.own = np.zeros(shape, dtype=np.int32)
        self.tocc = np.zeros(shape, dtype=np.int32)
        self.via_occ = np.zeros((self.ny, self.nx), dtype=np.int32)
        self.copper = {}
        self.netitem, self.nets, self.codes = {}, {}, {}
        for name, n in board.GetNetsByName().items():
            self.codes[str(name)] = n.GetNetCode(); self.nets[n.GetNetCode()] = str(name); self.netitem[n.GetNetCode()] = n
        self.unrouted = []
        self.added = 0
        self.pads = {}            # code -> [(layers, cx, cy, rect, minsize)]
        self.pad_cells_cache = {}
        self.width = {}           # code -> track width

        # --- 1) islands / rule areas
        for rectmm, layers, netname in nogo:
            if netname is None:                       # tank: no vias, tracks allowed
                self.stamp(self.via_occ, rectmm, BLOCK, 0.0)
                continue
            code = self.codes[netname]
            for l in layers:
                if l in LAY:
                    self.stamp(self.tocc[LAY[l]], rectmm, code, 0.0)
                    self.stamp(self.tocc[LAY[l]], rectmm, code, W_THICK / 2 + CLR)      # other nets keep clear
                    self.add_copper(code, LAY[l], rectmm, -0.3)                          # targets well inside the pour
            self.stamp(self.via_occ, rectmm, code, VIA_D / 2 + CLR)
        # --- 2) In1 5V island mask (shrunk ~1 mm)
        ys = Y0 + np.arange(self.ny) * G
        xs = X0 + np.arange(self.nx) * G
        self.island = np.zeros((self.ny, self.nx), dtype=bool)
        for iy, y in enumerate(ys):
            polys = island if isinstance(island[0][0], (list, tuple)) else [island]
            self.island[iy] = [any(point_in_poly(x, y, pg) for pg in polys) for x in xs]
        k = int(round(1.0 / G)); sh = self.island.copy()
        for dy in range(-k, k + 1):
            for dx in range(-k, k + 1):
                sh &= np.roll(np.roll(self.island, dy, 0), dx, 1)
        self.island = sh
        # --- 3) pads: first all halos, then bodies/lanes (so a body is never overwritten by a halo)
        plist = []
        for fp in board.GetFootprints():
            fc = fp.GetPosition(); fcx, fcy = ToMM(fc.x), ToMM(fc.y)
            for p in fp.Pads():
                code = p.GetNetCode()
                bb = p.GetBoundingBox()
                r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
                tht = p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD
                layers = [0, 1] if tht else [LAY.get(fp.GetLayer(), 0)]
                c = p.GetPosition()
                plist.append((code, layers, ToMM(c.x), ToMM(c.y), r, tht, fcx, fcy, len(fp.Pads())))
        gnd = self.codes.get('GND', -999)
        for code, layers, cx, cy, r, tht, fcx, fcy, npads in plist:
            for l in layers:
                self.stamp(self.pocc[l], r, code if code > 0 else BLOCK, PAD_M + (0.25 if (code == gnd and npads <= 3 and min(r[2] - r[0], r[3] - r[1]) >= 0.5) else 0.0))
            # other nets keep full clearance from the pad; the pad's own net may come close but never into the pad (no via-in-pad)
            self.stamp(self.via_occ, r, BLOCK if (tht or code <= 0) else code, VIA_D / 2 + CLR + 0.02)
            self.stamp(self.via_occ, r, BLOCK, VIA_D / 2 + 0.08, force=True)
        for code, layers, cx, cy, r, tht, fcx, fcy, npads in plist:
            if code <= 0 or self.nets.get(code) in SKIP or self.nets[code].startswith('unconnected-'):
                continue
            self.pads.setdefault(code, []).append((layers, cx, cy, r, min(r[2] - r[0], r[3] - r[1])))
        for code, pads in self.pads.items():
            self.width[code] = W_THICK if (self.nets[code] in THICK and min(p[4] for p in pads) >= 0.6) else W_DEFAULT
        for code, layers, cx, cy, r, tht, fcx, fcy, npads in plist:
            if code not in self.pads:
                continue
            w = self.width[code]
            body = self.body_cells(r, cx, cy, w)
            # escape lane: 1 mm from the pad body away from the footprint centre, along the dominant offset axis
            dx, dy = cx - fcx, cy - fcy
            lane = None
            if not tht:
                if abs(dx) >= abs(dy) and abs(dx) > 0.05:
                    lane = (r[2], r[1], r[2] + 1.2, r[3]) if dx > 0 else (r[0] - 1.2, r[1], r[0], r[3])
                elif abs(dy) > 0.05:
                    lane = (r[0], r[3], r[2], r[3] + 1.2) if dy > 0 else (r[0], r[1] - 1.2, r[2], r[1])
            for l in layers:
                for ix, iy in body:
                    self.own[l, iy, ix] = code; self.pocc[l, iy, ix] = code
                if lane:
                    for ix, iy in self.body_cells(lane, (lane[0] + lane[2]) / 2, (lane[1] + lane[3]) / 2, w):
                        if self.own[l, iy, ix] == 0 and self.pocc[l, iy, ix] in (0, code):
                            self.own[l, iy, ix] = code; self.pocc[l, iy, ix] = code
                            self.stamp(self.via_occ, self.mm(ix, iy) * 2, code, w / 2 + VIA_D / 2 + CLR)
        # island copper is not real copper where another net's pad (plus clearance) sits on it
        for code, cells in self.copper.items():
            self.copper[code] = {c for c in cells if self.pocc[c[0], c[2], c[1]] in (0, code)}
        # --- 4) existing tracks / vias
        for t in board.GetTracks():
            code = t.GetNetCode()
            c = code if code > 0 else BLOCK
            if isinstance(t, pcbnew.PCB_VIA):
                v = t.GetPosition(); x, y = ToMM(v.x), ToMM(v.y)
                try:
                    d = ToMM(t.GetWidth(F))
                except TypeError:
                    d = VIA_D
                for l in (0, 1):
                    self.stamp(self.tocc[l], (x, y, x, y), c, halo(d))
                    if c != BLOCK:
                        self.add_copper(c, l, (x, y, x, y), d / 2)
                self.stamp(self.via_occ, (x, y, x, y), BLOCK, d / 2 + VIA_D / 2 + CLR + 0.02)
            else:
                if t.GetLayer() not in LAY:
                    continue
                l = LAY[t.GetLayer()]
                a, e = t.GetStart(), t.GetEnd(); w = ToMM(t.GetWidth())
                self.stamp_seg(self.tocc[l], ToMM(a.x), ToMM(a.y), ToMM(e.x), ToMM(e.y), halo(w), c)
                self.stamp_seg(self.via_occ, ToMM(a.x), ToMM(a.y), ToMM(e.x), ToMM(e.y), w / 2 + VIA_D / 2 + CLR + 0.02, c)
                if c != BLOCK:
                    self.add_copper_seg(c, l, ToMM(a.x), ToMM(a.y), ToMM(e.x), ToMM(e.y), max(w / 2, 0.14))

    # ------------------------------------------------------------ raster helpers
    def cell(self, x, y):
        return int(round((x - X0) / G)), int(round((y - Y0) / G))

    def mm(self, ix, iy):
        return (X0 + ix * G, Y0 + iy * G)

    def _box(self, r, m):
        ix0, iy0 = self.cell(r[0] - m, r[1] - m); ix1, iy1 = self.cell(r[2] + m, r[3] + m)
        return max(ix0, 0), max(iy0, 0), min(ix1, self.nx - 1), min(iy1, self.ny - 1)

    def stamp(self, arr, r, code, m, force=False):
        ix0, iy0, ix1, iy1 = self._box(r, m)
        if ix1 < ix0 or iy1 < iy0:
            return
        sub = arr[iy0:iy1 + 1, ix0:ix1 + 1]
        if force:
            sub[:, :] = code
        else:
            conflict = (sub != 0) & (sub != code)
            sub[sub == 0] = code
            sub[conflict] = BLOCK

    def stamp_seg(self, arr, xa, ya, xb, yb, rad, code):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
        for i in range(n + 1):
            t = i / n
            self.stamp(arr, (xa + (xb - xa) * t, ya + (yb - ya) * t) * 2, code, rad)

    def add_copper(self, code, l, r, m):
        s = self.copper.setdefault(code, set())
        if r[2] > r[0] or r[3] > r[1]:                      # rectangle: cells whose centre is inside
            ix0 = int(math.ceil((r[0] - m - X0) / G - 1e-9)); ix1 = int(math.floor((r[2] + m - X0) / G + 1e-9))
            iy0 = int(math.ceil((r[1] - m - Y0) / G - 1e-9)); iy1 = int(math.floor((r[3] + m - Y0) / G + 1e-9))
            for iy in range(max(iy0, 0), min(iy1, self.ny - 1) + 1):
                for ix in range(max(ix0, 0), min(ix1, self.nx - 1) + 1):
                    s.add((l, ix, iy))
            return
        cx, cy = r[0], r[1]                                 # disc: cells whose centre is within the radius
        ix0, iy0, ix1, iy1 = self._box(r, m)
        rr = max(m - 0.02, 0.0) ** 2
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                x, y = self.mm(ix, iy)
                if (x - cx) ** 2 + (y - cy) ** 2 <= rr + 1e-9:
                    s.add((l, ix, iy))
        s.add((l,) + self.cell(cx, cy))

    def add_copper_seg(self, code, l, xa, ya, xb, yb, rad):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
        for i in range(n + 1):
            t = i / n
            self.add_copper(code, l, (xa + (xb - xa) * t, ya + (yb - ya) * t) * 2, rad)

    def body_cells(self, r, cx, cy, w):
        """grid cells a track of width w may be centred on while staying inside rect r (at least the centre row/col)"""
        def axis(lo, hi, c):
            cells = [i for i in range(int(math.ceil((lo + w / 2 - X0) / G)), int(math.floor((hi - w / 2 - X0) / G)) + 1)]
            return cells
        ixs = [i for i in range(int(math.ceil((r[0] + w / 2 - X0) / G - 1e-9)), int(math.floor((r[2] - w / 2 - X0) / G + 1e-9)) + 1)]
        iys = [i for i in range(int(math.ceil((r[1] + w / 2 - Y0) / G - 1e-9)), int(math.floor((r[3] - w / 2 - Y0) / G + 1e-9)) + 1)]
        if not ixs:
            ixs = [self.cell(cx, cy)[0]]
        if not iys:
            iys = [self.cell(cx, cy)[1]]
        return [(ix, iy) for ix in ixs for iy in iys if 0 <= ix < self.nx and 0 <= iy < self.ny]

    # ------------------------------------------------------------ search
    def free(self, l, ix, iy, code):
        t = self.tocc[l, iy, ix]
        if t != 0 and t != code:
            return False
        p = self.pocc[l, iy, ix]
        return p == 0 or p == code or self.own[l, iy, ix] == code

    def via_ok(self, ix, iy, code):
        v = self.via_occ[iy, ix]
        return (v == 0 or v == code) and self.free(0, ix, iy, code) and self.free(1, ix, iy, code) \
            and self.own[0, iy, ix] == 0 and self.own[1, iy, ix] == 0

    def dist_field(self, cx, cy, rad):
        """admissible heuristic (grid units): euclidean distance to a disc around (cx, cy)"""
        xs = X0 + np.arange(self.nx) * G
        ys = Y0 + np.arange(self.ny) * G
        d = np.hypot(xs[None, :] - cx, ys[:, None] - cy) - rad
        return np.maximum(d, 0.0) / G

    def search(self, code, sources, targets, hfield=None, plane=False, max_expand=None, max_len=None):
        def h(ix, iy):
            return float(hfield[iy, ix]) if hfield is not None else 0.0
        heap, best, prev, done = [], {}, {}, set()
        for s in sources:
            best[s] = 0.0; heapq.heappush(heap, (h(s[1], s[2]), 0.0, s, (0, 0)))
        steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
        expanded = 0
        while heap:
            f, g, cur, d = heapq.heappop(heap)
            if cur in done:
                continue
            done.add(cur)
            expanded += 1
            if expanded > (max_expand or MAX_EXPAND):
                return None
            l, ix, iy = cur
            if cur in targets or (plane and cur not in sources and self.island[iy, ix] and self.via_ok(ix, iy, code)):
                path = [cur]
                while cur in prev:
                    cur = prev[cur]; path.append(cur)
                if max_len is not None and len(path) > max_len:
                    return None
                return path[::-1]
            for dx, dy, c in steps:
                nx_, ny_ = ix + dx, iy + dy
                if nx_ < 0 or ny_ < 0 or nx_ >= self.nx or ny_ >= self.ny:
                    continue
                if not self.free(l, nx_, ny_, code):
                    continue
                if dx and dy and not (self.free(l, ix + dx, iy, code) and self.free(l, ix, iy + dy, code)):
                    continue
                ng = g + c + (TURN_COST if d != (dx, dy) and d != (0, 0) else 0.0)
                nxt = (l, nx_, ny_)
                if ng < best.get(nxt, 1e18):
                    best[nxt] = ng; prev[nxt] = cur
                    heapq.heappush(heap, (ng + h(nx_, ny_), ng, nxt, (dx, dy)))
            if self.via_ok(ix, iy, code):
                nxt = (1 - l, ix, iy); ng = g + VIA_COST
                if ng < best.get(nxt, 1e18):
                    best[nxt] = ng; prev[nxt] = cur
                    heapq.heappush(heap, (ng + h(ix, iy), ng, nxt, (0, 0)))
        return None

    # ------------------------------------------------------------ geometry out
    def add_track(self, code, l, xa, ya, xb, yb, width):
        if math.hypot(xb - xa, yb - ya) < 1e-3:
            return
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(VECTOR2I(FromMM(xa), FromMM(ya))); t.SetEnd(VECTOR2I(FromMM(xb), FromMM(yb)))
        t.SetWidth(FromMM(width)); t.SetLayer(F if l == 0 else B); t.SetNet(self.netitem[code]); self.b.Add(t)
        self.added += 1
        self.stamp_seg(self.tocc[l], xa, ya, xb, yb, halo(width), code)
        self.stamp_seg(self.via_occ, xa, ya, xb, yb, width / 2 + VIA_D / 2 + CLR + 0.02, code)
        self.add_copper_seg(code, l, xa, ya, xb, yb, 0.14)

    def add_via(self, code, ix, iy):
        x, y = self.mm(ix, iy)
        v = pcbnew.PCB_VIA(self.b); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        v.SetDrill(FromMM(VIA_DRILL)); v.SetWidth(FromMM(VIA_D)); v.SetLayerPair(F, B); v.SetNet(self.netitem[code])
        self.b.Add(v); self.added += 1
        for l in (0, 1):
            self.stamp(self.tocc[l], (x, y, x, y), code, halo(VIA_D))
            self.add_copper(code, l, (x, y, x, y), VIA_D / 2)
        self.stamp(self.via_occ, (x, y, x, y), BLOCK, VIA_D + CLR + 0.02)

    def emit(self, code, path, width, anchors):
        """path -> tracks + vias; anchors: cell -> pad centre, used to tie path ends into pad bodies"""
        runs, cur = [], [path[0]]
        for p in path[1:]:
            if p[0] != cur[-1][0]:
                runs.append(cur); cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        if path[0] in anchors:
            ax, ay = anchors[path[0]]; x, y = self.mm(path[0][1], path[0][2])
            self.add_track(code, path[0][0], ax, ay, x, y, width)
        for i, run in enumerate(runs):
            l = run[0][0]
            pts = [run[0]]
            for a, b_, c in zip(run, run[1:], run[2:]):
                if (b_[1] - a[1], b_[2] - a[2]) != (c[1] - b_[1], c[2] - b_[2]):
                    pts.append(b_)
            if run[-1] != pts[-1]:
                pts.append(run[-1])
            for a, b_ in zip(pts, pts[1:]):
                xa, ya = self.mm(a[1], a[2]); xb, yb = self.mm(b_[1], b_[2])
                self.add_track(code, l, xa, ya, xb, yb, width)
            if i < len(runs) - 1:
                self.add_via(code, run[-1][1], run[-1][2])
        if path[-1] in anchors:
            ax, ay = anchors[path[-1]]; x, y = self.mm(path[-1][1], path[-1][2])
            self.add_track(code, path[-1][0], x, y, ax, ay, width)

    # ------------------------------------------------------------ nets
    def pad_cells(self, code, pad):
        layers, cx, cy, r, ms = pad
        key = (code, cx, cy)
        if key not in self.pad_cells_cache:
            out = set()
            ix0, iy0, ix1, iy1 = self._box(r, 0.0)
            for l in layers:
                for iy in range(iy0, iy1 + 1):
                    for ix in range(ix0, ix1 + 1):
                        if self.own[l, iy, ix] == code:
                            out.add((l, ix, iy))
            self.pad_cells_cache[key] = out
        return self.pad_cells_cache[key]

    def groups(self, code, pads):
        """cells of all same-net pads whose bodies touch a given pad (transitively)"""
        n = len(pads)
        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for i in range(n):
            for j in range(i + 1, n):
                a, b = pads[i][3], pads[j][3]
                if a[0] <= b[2] + 0.02 and b[0] <= a[2] + 0.02 and a[1] <= b[3] + 0.02 and b[1] <= a[3] + 0.02 and set(pads[i][0]) & set(pads[j][0]):
                    parent[find(i)] = find(j)
        out = {}
        for i in range(n):
            out.setdefault(find(i), set()).update(self.pad_cells(code, pads[i]))
        return {i: out[find(i)] for i in range(n)}

    def route_net(self, code, plane=False):
        name = self.nets[code]
        pads = self.pads.get(code, [])
        width = self.width[code]
        anchors = {}
        for pad in pads:
            for c in self.pad_cells(code, pad):
                anchors[c] = (pad[1], pad[2])
        grp = self.groups(code, pads)
        gcells = {(p[1], p[2]): grp[i] for i, p in enumerate(pads)}
        connected = set(self.copper.get(code, set()))
        if plane:
            for pad in pads:
                pc = self.pad_cells(code, pad)
                if not pc:
                    self.unrouted.append((name, pad[1], pad[2])); continue
                if gcells[(pad[1], pad[2])] & connected:
                    connected |= gcells[(pad[1], pad[2])]; continue
                existing = set(self.copper.get(code, set()))
                path = None
                if existing:                      # nearby 5V copper (a cap already tied to the plane): join it, no new via
                    path = self.search(code, pc, existing, max_expand=25000, max_len=40)
                if path is None:
                    path = self.search(code, pc, existing, plane=True)
                if path is None:
                    self.unrouted.append((name, pad[1], pad[2])); continue
                self.emit(code, path, width, anchors)
                end = path[-1]
                if end not in existing:          # ended on the plane, not on existing 5V copper -> via into In1
                    self.add_via(code, end[1], end[2])
                connected |= set(path) | gcells[(pad[1], pad[2])] | self.copper.get(code, set())
            return
        remaining = sorted(pads, key=lambda p: (p[1], p[2]))
        if not connected:
            while remaining:
                first = remaining.pop(0)
                connected = set(gcells[(first[1], first[2])])
                if connected:
                    break
                self.unrouted.append((name, first[1], first[2]))
        while remaining:
            cxs = np.fromiter((self.mm(ix, iy)[0] for l, ix, iy in connected), float, len(connected))
            cys = np.fromiter((self.mm(ix, iy)[1] for l, ix, iy in connected), float, len(connected))
            remaining.sort(key=lambda p: float(np.min(np.hypot(cxs - p[1], cys - p[2]))))
            pad = remaining.pop(0)
            pc = self.pad_cells(code, pad)
            if not pc:
                self.unrouted.append((name, pad[1], pad[2])); continue
            if gcells[(pad[1], pad[2])] & connected:
                connected |= gcells[(pad[1], pad[2])]; continue
            hf = self.dist_field(pad[1], pad[2], max(pad[3][2] - pad[3][0], pad[3][3] - pad[3][1]) / 2)
            path = self.search(code, connected, pc, hfield=hf)
            if path is None:
                self.unrouted.append((name, pad[1], pad[2])); continue
            self.emit(code, path, width, anchors)
            connected |= set(path) | gcells[(pad[1], pad[2])]


def _explain(self, name, x, y):
    code = self.codes[name]
    pad = min(self.pads[code], key=lambda p: (p[1] - x) ** 2 + (p[2] - y) ** 2)
    pc = self.pad_cells(code, pad)
    seen, stack = set(pc), list(pc)
    while stack and len(seen) < 4000:
        l, ix, iy = stack.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (l, ix + dx, iy + dy)
                if n in seen or not (0 <= n[1] < self.nx and 0 <= n[2] < self.ny):
                    continue
                if self.free(l, n[1], n[2], code):
                    seen.add(n); stack.append(n)
        if self.via_ok(ix, iy, code) and (1 - l, ix, iy) not in seen:
            seen.add((1 - l, ix, iy)); stack.append((1 - l, ix, iy))
    xs = [self.mm(ix, iy)[0] for l, ix, iy in seen]; ys = [self.mm(ix, iy)[1] for l, ix, iy in seen]
    layers = sorted({l for l, ix, iy in seen})
    print(f'   unrouted {name} pad@({x:.2f},{y:.2f}) layers{pad[0]} cells {len(pc)} reach {len(seen)} '
          f'bbox x[{min(xs):.1f},{max(xs):.1f}] y[{min(ys):.1f},{max(ys):.1f}] layers {layers}')


Router.explain = _explain


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        xa, ya = poly[i]; xb, yb = poly[(i + 1) % n]
        if (ya > y) != (yb > y):
            xi = xa + (y - ya) * (xb - xa) / (yb - ya)
            if x < xi:
                inside = not inside
    return inside


def route_all(board, nogo, fiveV_island, board_rect=None):
    r = Router(board, nogo, fiveV_island)
    zone_nets = {'S1', 'S2', 'Out+'}
    order = [(code, r.nets[code]) for code in r.pads]

    def key(cn):
        code, name = cn
        pads = r.pads[code]
        span = (max(p[1] for p in pads) - min(p[1] for p in pads)) + (max(p[2] for p in pads) - min(p[2] for p in pads))
        return (0 if name in zone_nets else 2 if name == '5V' else 1 if (span < 15.0 and name not in THICK) else 3 if name in THICK else 4, len(pads), span)
    order.sort(key=key)
    import os, random
    seed = int(os.environ.get('ROUTE_SEED', '0'))
    if seed:
        rnd = random.Random(seed)
        groups = {}
        for cn in order:
            groups.setdefault(key(cn)[0], []).append(cn)
        order = []
        for k in sorted(groups):
            g = groups[k]; rnd.shuffle(g); order += g
    print('router: seed', seed)
    import time
    for code, name in order:
        t0 = time.time(); n0 = len(r.unrouted); a0 = r.added
        r.route_net(code, plane=(name == '5V'))
        print(f'  net {name:32s} pads {len(r.pads[code]):3d}  items +{r.added - a0:3d}  unrouted +{len(r.unrouted) - n0}  {time.time() - t0:5.1f}s', flush=True)
    print('router: added', r.added, 'items; unrouted:', len(r.unrouted))
    for name, x, y in r.unrouted:
        r.explain(name, x, y)
    return r.unrouted

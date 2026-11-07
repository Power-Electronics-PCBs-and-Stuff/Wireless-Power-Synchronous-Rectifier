#!/usr/bin/env python
"""
check_board.py -- standalone verification report for a KiCad 10 PCB.

Run with KiCad's bundled python:
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" check_board.py <board.kicad_pcb> [--sample <sample.kicad_pcb>] [--drc]
"""
import sys
import os
import argparse
import subprocess
from collections import defaultdict, Counter

import pcbnew

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
KEY_NETS = ["GND", "5V", "S1", "S2", "Out+"]
EDGE_LIMIT_MM = 12.0
NARROW_TRACK_MM = 0.2


def mm(v):
    return pcbnew.ToMM(int(v))


def fmt(v, nd=3):
    return "{:.{}f}".format(v, nd)


def hr(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def layer_names(board, layer_set):
    names = []
    try:
        for lid in layer_set.Seq():
            try:
                names.append(board.GetLayerName(lid))
            except Exception:
                names.append(str(lid))
    except Exception:
        names.append("n/a")
    return names


def load(path):
    board = pcbnew.LoadBoard(path)
    try:
        board.BuildConnectivity()
    except Exception as e:
        print("warning: BuildConnectivity failed: %s" % e)
    return board


def split_tracks(board):
    tracks, vias = [], []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            vias.append(t)
        else:
            tracks.append(t)
    return tracks, vias


def zone_area_mm2(zone, layer):
    try:
        polys = zone.GetFilledPolysList(layer)
    except Exception:
        return None
    for meth in ("TotalArea", "Area"):
        try:
            a = getattr(polys, meth)()
            return a / 1e12  # nm^2 -> mm^2
        except Exception:
            continue
    return None


def unconnected_count(board):
    try:
        return board.GetConnectivity().GetUnconnectedCount(True)
    except Exception:
        try:
            return board.GetConnectivity().GetUnconnectedCount()
        except Exception:
            return None


def basic_stats(board):
    fps = list(board.GetFootprints())
    tracks, vias = split_tracks(board)
    zones = list(board.Zones())
    bbox = board.GetBoardEdgesBoundingBox()
    try:
        layers = board.GetDesignSettings().GetCopperLayerCount()
    except Exception:
        layers = None
    zone_nets = set()
    for z in zones:
        try:
            n = z.GetNetname()
            if n:
                zone_nets.add(n)
        except Exception:
            pass
    gnd_vias = sum(1 for v in vias if v.GetNetname() == "GND")
    has_outline = bbox.GetWidth() > 0 and bbox.GetHeight() > 0
    return {
        "fps": fps,
        "tracks": tracks,
        "vias": vias,
        "zones": zones,
        "bbox": bbox,
        "has_outline": has_outline,
        "layers": layers,
        "zone_nets": zone_nets,
        "gnd_vias": gnd_vias,
        "unconnected": unconnected_count(board),
    }


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def section_summary(board, st):
    hr("1. SUMMARY")
    bb = st["bbox"]
    x0, y0 = mm(bb.GetLeft()), mm(bb.GetTop())
    x1, y1 = mm(bb.GetRight()), mm(bb.GetBottom())
    w, h = x1 - x0, y1 - y0
    print("Footprints          : %d" % len(st["fps"]))
    print("Copper layers       : %s" % st["layers"])
    print("Board bbox (mm)     : (%s, %s) - (%s, %s)" % (fmt(x0), fmt(y0), fmt(x1), fmt(y1)))
    print("Board size (mm)     : %s x %s%s" % (fmt(w), fmt(h),
          "" if st["has_outline"] else "   ** NO Edge.Cuts OUTLINE FOUND **"))
    print("Tracks              : %d" % len(st["tracks"]))
    print("Vias                : %d" % len(st["vias"]))
    print("Zones               : %d" % len(st["zones"]))
    u = st["unconnected"]
    print("Unconnected ratsnest: %s" % ("n/a" if u is None else u))


def section_vias(st):
    hr("2. VIA COUNTS PER NET")
    c = Counter(v.GetNetname() for v in st["vias"])
    for n in KEY_NETS:
        print("  %-12s : %d" % (n, c.get(n, 0)))
    print("Top 10 nets by via count:")
    if not c:
        print("  (no vias)")
    for n, k in c.most_common(10):
        print("  %-24s : %d" % (n or "<no net>", k))


def section_footprints(board, st):
    hr("3. FOOTPRINT PLACEMENT")
    bb = st["bbox"]
    bx0, by0, bx1, by1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
    outside = []
    back = []
    for fp in st["fps"]:
        ref = fp.GetReference()
        try:
            fb = fp.GetBoundingBox(False, False)  # exclude text / invisible
        except TypeError:
            fb = fp.GetBoundingBox()
        if st["has_outline"] and (fb.GetLeft() < bx0 or fb.GetTop() < by0 or
                                  fb.GetRight() > bx1 or fb.GetBottom() > by1):
            outside.append(ref)
        try:
            if fp.GetLayer() == pcbnew.B_Cu:
                back.append(ref)
        except Exception:
            pass
    if not st["has_outline"]:
        print("Footprints with bbox outside board edges: n/a (no board outline)")
    else:
        print("Footprints with bbox outside board edges: %d" % len(outside))
        if outside:
            print("  " + ", ".join(sorted(outside)))
    print("Footprints on back layer (B.Cu): %d" % len(back))
    if back:
        print("  " + ", ".join(sorted(back)))


def section_connectors(st):
    hr("4. CONNECTOR EDGE CHECK (within %.1f mm of a board edge)" % EDGE_LIMIT_MM)
    bb = st["bbox"]
    bx0, by0 = mm(bb.GetLeft()), mm(bb.GetTop())
    bx1, by1 = mm(bb.GetRight()), mm(bb.GetBottom())
    found = False
    for fp in st["fps"]:
        ref = fp.GetReference()
        val = fp.GetValue() or ""
        if not (ref.startswith("J") or "XT60" in val.upper()):
            continue
        found = True
        p = fp.GetPosition()
        cx, cy = mm(p.x), mm(p.y)
        if not st["has_outline"]:
            print("  %-8s %-24s centre=(%s, %s)  dist-to-edge=n/a (no board outline)" % (
                ref, val[:24], fmt(cx, 2), fmt(cy, 2)))
            continue
        d = min(cx - bx0, bx1 - cx, cy - by0, by1 - cy)
        if d < 0:
            verdict = "OUTSIDE BOARD"
        elif d <= EDGE_LIMIT_MM:
            verdict = "OK"
        else:
            verdict = "FAR FROM EDGE"
        print("  %-8s %-24s centre=(%s, %s)  dist-to-edge=%s mm  %s" % (
            ref, val[:24], fmt(cx, 2), fmt(cy, 2), fmt(d, 2), verdict))
    if not found:
        print("  (no J* / XT60 footprints found)")


def section_zones(board, st):
    hr("5. ZONES")
    if not st["zones"]:
        print("  (no zones)")
        return
    for i, z in enumerate(st["zones"]):
        net = z.GetNetname() or "<no net>"
        lset = z.GetLayerSet()
        lnames = layer_names(board, lset)
        prio = "n/a"
        for meth in ("GetAssignedPriority", "GetPriority"):
            try:
                prio = getattr(z, meth)()
                break
            except Exception:
                continue
        try:
            filled = z.IsFilled()
        except Exception:
            filled = "n/a"
        areas = []
        if filled is True:
            try:
                for lid in lset.Seq():
                    a = zone_area_mm2(z, lid)
                    if a is not None:
                        areas.append("%s=%.1f" % (board.GetLayerName(lid), a))
            except Exception:
                pass
        extra = ""
        try:
            if z.GetIsRuleArea():
                extra = " [rule area]"
        except Exception:
            pass
        print("  zone %2d: net=%-14s layers=%-20s prio=%-3s filled=%-5s area_mm2=%s%s" % (
            i, net, ",".join(lnames), prio, filled,
            " ".join(areas) if areas else "n/a", extra))


def section_pads(board, st):
    hr("6. PAD CONNECTIVITY (informational)")
    pad_by_net = defaultdict(list)
    for fp in st["fps"]:
        for pad in fp.Pads():
            n = pad.GetNetname()
            if not n or n.startswith("unconnected-"):
                continue
            pad_by_net[n].append("%s.%s" % (fp.GetReference(), pad.GetNumber()))
    trk_by_net = Counter(t.GetNetname() for t in st["tracks"])
    via_by_net = Counter(v.GetNetname() for v in st["vias"])
    zone_nets = st["zone_nets"]

    lonely = []       # nets with exactly 1 pad, nothing else
    no_copper = []    # nets with >1 pad but no tracks/vias/zones
    for n, pads in sorted(pad_by_net.items()):
        has_copper = trk_by_net.get(n, 0) or via_by_net.get(n, 0) or (n in zone_nets)
        if len(pads) == 1 and not has_copper:
            lonely.append((n, pads))
        elif len(pads) > 1 and not has_copper:
            no_copper.append((n, len(pads)))

    # Optional: connectivity API -- pads with nothing else connected to them
    # Optional: connectivity API -- pads with nothing else connected to them.
    # KiCad 10 python binding: GetConnectedItems(item) (no type list) works;
    # the returned list includes the pad itself, so filter it out by UUID.
    isolated_pads = None
    try:
        conn = board.GetConnectivity()
        isolated_pads = []
        for fp in st["fps"]:
            for pad in fp.Pads():
                n = pad.GetNetname()
                if not n or n.startswith("unconnected-"):
                    continue
                items = conn.GetConnectedItems(pad)
                pad_uuid = str(pad.m_Uuid.AsString()) if hasattr(pad.m_Uuid, "AsString") else str(pad.m_Uuid)
                others = []
                for it in items:
                    try:
                        u = str(it.m_Uuid.AsString()) if hasattr(it.m_Uuid, "AsString") else str(it.m_Uuid)
                    except Exception:
                        u = None
                    if u != pad_uuid:
                        others.append(it)
                if len(others) == 0:
                    isolated_pads.append("%s.%s[%s]" % (fp.GetReference(), pad.GetNumber(), n))
    except Exception as e:
        print("  (connectivity API unavailable: %s)" % str(e).splitlines()[0][:120])
        isolated_pads = None

    print("Nets with pads: %d" % len(pad_by_net))
    print("Nets with >1 pad and NO tracks/vias/zones: %d" % len(no_copper))
    for n, k in no_copper[:40]:
        print("  %-24s pads=%d" % (n, k))
    if len(no_copper) > 40:
        print("  ... (%d more)" % (len(no_copper) - 40))
    print("Single-pad nets with no copper (informational): %d" % len(lonely))
    for n, pads in lonely[:20]:
        print("  %-24s %s" % (n, pads[0]))
    if len(lonely) > 20:
        print("  ... (%d more)" % (len(lonely) - 20))
    if isolated_pads is None:
        print("Pads with no copper connection (connectivity API): n/a")
    else:
        print("Pads with no copper connection (connectivity API): %d" % len(isolated_pads))
        for s in isolated_pads[:40]:
            print("  " + s)
        if len(isolated_pads) > 40:
            print("  ... (%d more)" % (len(isolated_pads) - 40))


def section_track_widths(st):
    hr("7. TRACK WIDTH STATISTICS")
    widths = defaultdict(list)
    for t in st["tracks"]:
        try:
            widths[t.GetNetname()].append(mm(t.GetWidth()))
        except Exception:
            pass
    for n in KEY_NETS:
        ws = widths.get(n)
        if ws:
            print("  %-12s : n=%-5d min=%s  max=%s mm" % (n, len(ws), fmt(min(ws)), fmt(max(ws))))
        else:
            print("  %-12s : (no tracks)" % n)
    allw = [w for ws in widths.values() for w in ws]
    if allw:
        print("Overall min track width : %s mm" % fmt(min(allw)))
        print("Overall max track width : %s mm" % fmt(max(allw)))
        narrow = sum(1 for w in allw if w < NARROW_TRACK_MM)
        print("Tracks narrower than %.2f mm : %d" % (NARROW_TRACK_MM, narrow))
    else:
        print("  (no tracks on board)")


def section_compare(board, st, sample_path):
    hr("8. COMPARISON WITH SAMPLE: %s" % os.path.basename(sample_path))
    sb = load(sample_path)
    ss = basic_stats(sb)

    def size(s):
        bb = s["bbox"]
        return "%s x %s" % (fmt(mm(bb.GetWidth()), 1), fmt(mm(bb.GetHeight()), 1))

    rows = [
        ("Copper layers", st["layers"], ss["layers"]),
        ("Board size (mm)", size(st), size(ss)),
        ("Footprints", len(st["fps"]), len(ss["fps"])),
        ("Tracks", len(st["tracks"]), len(ss["tracks"])),
        ("Vias", len(st["vias"]), len(ss["vias"])),
        ("Zones", len(st["zones"]), len(ss["zones"])),
        ("Distinct zone nets", len(st["zone_nets"]), len(ss["zone_nets"])),
        ("GND vias", st["gnd_vias"], ss["gnd_vias"]),
        ("Unconnected", st["unconnected"], ss["unconnected"]),
    ]
    print("  %-22s %18s %18s" % ("metric", "board", "sample"))
    print("  " + "-" * 60)
    for name, a, b in rows:
        print("  %-22s %18s %18s" % (name, a, b))
    sz = sorted(st["zone_nets"])
    sz2 = sorted(ss["zone_nets"])
    print("  board zone nets : %s" % (", ".join(sz) if sz else "-"))
    print("  sample zone nets: %s" % (", ".join(sz2) if sz2 else "-"))


# --------------------------------------------------------------------------
# DRC
# --------------------------------------------------------------------------

def parse_drc_report(path):
    """Group entries by '[rule]' header line. Returns (Counter, {rule: first header line})."""
    counts = Counter()
    examples = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n")
            if s.startswith("[") and "]" in s:
                rule = s[1:s.index("]")]
                counts[rule] += 1
                if rule not in examples:
                    examples[rule] = s[:200]
    return counts, examples


def run_drc(board_path):
    hr("DRC (kicad-cli)")
    rpt = board_path + ".drc.rpt"
    cmd = [KICAD_CLI, "pcb", "drc", "-o", rpt, "--severity-all", "--units", "mm", board_path]
    print("Running: " + " ".join('"%s"' % c if " " in c else c for c in cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print("DRC timed out after 600 s")
        return
    except FileNotFoundError:
        print("kicad-cli not found at %s" % KICAD_CLI)
        return
    print("kicad-cli exit code: %d" % r.returncode)
    if r.stdout and r.stdout.strip():
        print("stdout: " + r.stdout.strip()[:400])
    if r.stderr and r.stderr.strip():
        err = [l for l in r.stderr.splitlines() if "duplicate image handler" not in l and l.strip()]
        if err:
            print("stderr: " + "\n".join(err)[:400])
    if not os.path.exists(rpt):
        print("No DRC report produced.")
        return
    counts, examples = parse_drc_report(rpt)
    print("Report: %s" % rpt)
    print("Total violations: %d   distinct rule ids: %d" % (sum(counts.values()), len(counts)))
    print("Top 15 rule ids:")
    for rule, k in counts.most_common(15):
        print("  %-36s %d" % (rule, k))
    print("Examples (5 most common):")
    for rule, k in counts.most_common(5):
        print("  [%s] -> %s" % (rule, examples.get(rule, "")))
    # kicad-cli summary lines, e.g. '** Found N DRC violations **'
    try:
        with open(rpt, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("**"):
                    print("  " + line.strip())
    except Exception:
        pass


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="KiCad 10 PCB verification report")
    ap.add_argument("board")
    ap.add_argument("--sample", default=None)
    ap.add_argument("--drc", action="store_true")
    args = ap.parse_args()

    board_path = os.path.abspath(args.board)
    print("Board: %s" % board_path)
    try:
        print("pcbnew version: %s" % pcbnew.GetBuildVersion())
    except Exception:
        pass

    board = load(board_path)
    st = basic_stats(board)

    section_summary(board, st)
    section_vias(st)
    section_footprints(board, st)
    section_connectors(st)
    section_zones(board, st)
    section_pads(board, st)
    section_track_widths(st)
    if args.sample:
        section_compare(board, st, os.path.abspath(args.sample))
    if args.drc:
        run_drc(board_path)
    print()
    print("Done.")


if __name__ == "__main__":
    main()

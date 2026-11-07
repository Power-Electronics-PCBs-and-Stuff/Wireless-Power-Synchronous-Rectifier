import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
mm = lambda v: round(pcbnew.ToMM(v), 1)
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for l in z.GetLayerSet().Seq():
        ps = z.GetFilledPolysList(l)
        n = ps.OutlineCount()
        if n > 1:
            areas = []
            for i in range(n):
                o = ps.Outline(i); bb = o.BBox()
                areas.append((round(abs(o.Area()) / 1e6, 1), mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
            areas.sort()
            print(z.GetNetname(), pcbnew.BOARD.GetStandardLayerName(l), 'outlines', n, 'smallest:', areas[:6])

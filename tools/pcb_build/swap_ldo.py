"""swap_ldo.py <in.kicad_pcb> <out.kicad_pcb> <footprint name>
Replace U4 (TPS7A25 DRV) by the schematic's U5 (TPS7A2650DRVR, lib TPS7A2650DRVR) in place. Nothing else is touched
except the net name Net-(U4-EN) -> Net-(U5-EN) (schematic name) and a zone refill."""
import sys, pcbnew
SRC, DST, FPNAME = sys.argv[1:4]
LIB = 'C:/Users/Vedant/Documents/KiCad/Guad_Rectifier/Synchronous Rectifier/libs/TPS7A2650DRVR/KiCADv6/footprints.pretty'
NETS = {'1': '5V', '2': 'GND', '3': 'GND', '4': 'Net-(U5-EN)', '5': 'GND', '6': 'Net-(U5-EN)', '7': 'GND', 'V': 'GND'}   # from the exported netlist; V = vias in the GND pad
b = pcbnew.LoadBoard(SRC)
old = b.FindFootprintByReference('U4'); assert old is not None
assert {p.GetNumber(): p.GetNetname() for p in old.Pads()} == {'1': '5V', '2': 'GND', '3': 'GND', '4': 'Net-(U4-EN)', '5': 'GND', '6': 'Net-(U4-EN)', '7': 'GND'}
en = b.FindNet('Net-(U4-EN)'); assert en is not None and b.FindNet('Net-(U5-EN)') is None
en.SetNetname('Net-(U5-EN)')
new = pcbnew.FootprintLoad(LIB, FPNAME); assert new is not None
new.SetFPID(pcbnew.LIB_ID('TPS7A2650DRVR', FPNAME))
new.SetReference('U5'); new.SetValue('TPS7A2650DRVR')
new.SetPosition(old.GetPosition()); new.SetOrientationDegrees(old.GetOrientationDegrees())
assert old.GetLayer() == pcbnew.F_Cu
new.SetPath(pcbnew.KIID_PATH('/434234d0-07e0-4bdb-9fb3-0fb201cfd31f'))
new.SetAttributes(old.GetAttributes())
r0, r1 = old.Reference(), new.Reference()
r1.SetPosition(r0.GetPosition()); r1.SetTextSize(r0.GetTextSize()); r1.SetTextThickness(r0.GetTextThickness())
r1.SetLayer(r0.GetLayer()); r1.SetVisible(r0.IsVisible()); r1.SetTextAngleDegrees(0)
r1.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); r1.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
for p in new.Pads():
    n = b.FindNet(NETS[p.GetNumber()]) if NETS[p.GetNumber()] != 'Net-(U5-EN)' else en
    assert n is not None, p.GetNumber()
    p.SetNet(n)
    if p.GetNetname() == 'GND':
        p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)      # as on the old footprint (multi-pad parts: solid GND)
b.Remove(old); b.Add(new)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(DST, b)
print('swapped U4 ->', new.GetReference(), new.GetFPIDAsString(), [(p.GetNumber(), p.GetNetname()) for p in new.Pads()])

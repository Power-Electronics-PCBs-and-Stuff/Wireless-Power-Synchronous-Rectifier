"""Post-process: copy the sample's stackup block into the board file, write net classes into the .kicad_pro.

usage: python finish.py <board.kicad_pcb> <sample.kicad_pcb> <project.kicad_pro>
"""
import json
import re
import sys

PCB, SAMPLE, PRO = sys.argv[1:4]


def block(text, start):
    """return (s, e) of the s-expression starting at text.find(start)"""
    s = text.index(start)
    depth = 0
    i = s
    while True:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return s, i + 1
        i += 1


sample = open(SAMPLE, encoding='utf8').read()
ss, se = block(sample, '(stackup')
stack = sample[ss:se]
pcb = open(PCB, encoding='utf8').read()
if '(stackup' in pcb:
    a, b = block(pcb, '(stackup')
    pcb = pcb[:a] + stack + pcb[b:]
else:
    i = pcb.index('(setup') + len('(setup')
    pcb = pcb[:i] + '\n\t\t' + stack + pcb[i:]
pcb = re.sub(r'(\(layer "(?:F|B)\.Cu"\s*\(type "copper"\)\s*\(thickness )0\.035\)', lambda m: m.group(1) + '0.07)', pcb)   # 2 oz outer copper
open(PCB, 'w', encoding='utf8', newline='\n').write(pcb)

pro = json.load(open(PRO, encoding='utf8'))
ns = pro.setdefault('net_settings', {})
classes = ns.setdefault('classes', [])
default = next((c for c in classes if c.get('name') == 'Default'), None)
if default is None:
    default = {'name': 'Default'}; classes.append(default)
default.update({'clearance': 0.2, 'track_width': 0.25, 'via_diameter': 0.6, 'via_drill': 0.3,
                'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.2, 'diff_pair_gap': 0.25,
                'diff_pair_via_gap': 0.25, 'bus_width': 12, 'wire_width': 6, 'line_style': 0,
                'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'priority': 2147483647})
classes[:] = [c for c in classes if c.get('name') not in ('Power', 'Supply')]
classes.append({**{k: v for k, v in default.items()}, 'name': 'Power', 'track_width': 1.0, 'clearance': 0.2, 'priority': 0,
                'pcb_color': 'rgba(255, 128, 0, 0.700)'})
classes.append({**{k: v for k, v in default.items()}, 'name': 'Supply', 'track_width': 0.35, 'priority': 1,
                'pcb_color': 'rgba(0, 200, 255, 0.700)'})
ns['netclass_patterns'] = [
    {'netclass': 'Power', 'pattern': 'S1'}, {'netclass': 'Power', 'pattern': 'S2'}, {'netclass': 'Power', 'pattern': 'Out+'},
    {'netclass': 'Power', 'pattern': 'GND'}, {'netclass': 'Power', 'pattern': 'Is-'},
    {'netclass': 'Power', 'pattern': 'Net-(C1-Pad1)'}, {'netclass': 'Power', 'pattern': 'Net-(ReceiverCoil1-Pin_2)'},
    {'netclass': 'Supply', 'pattern': '5V'}, {'netclass': 'Supply', 'pattern': '-5V'}, {'netclass': 'Supply', 'pattern': 'Net-(U4-EN)'},
]
rules = pro.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {})
rules.update({'min_clearance': 0.2, 'min_track_width': 0.2, 'min_via_diameter': 0.5, 'min_through_hole_diameter': 0.3,
              'min_copper_edge_clearance': 0.5, 'min_hole_clearance': 0.25, 'min_hole_to_hole': 0.25, 'min_resolved_spokes': 1})
json.dump(pro, open(PRO, 'w', encoding='utf8'), indent=2)
print('finish: stackup patched, net classes written')

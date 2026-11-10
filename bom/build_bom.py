"""Fill bom/bom.csv with the parts verified on digikey.com (2026-11-09), write the schematic property update JSON
and a DigiKey cost estimate. Run from the project folder: python bom/build_bom.py"""
import csv, json, os

# references -> (MPN, manufacturer, DigiKey cut-tape PN, DK stock, price qty1, price qty10, note)
P = {
    'BT1': ('BC4AAB', 'MPD', 'BC4AAB-ND', 16, 2.77, 2.30, 'DigiKey shows 16 on hand + 13,400 factory stock'),
    'C1,C58': ('', '', '', '', 0, 0, 'UNSOURCED: 33 nF in series with the coil sees ~11 A RMS and ~210 V RMS at 250 kHz; no single 1206 part exists. '
               'Needs a parallel C0G bank (e.g. 10x KEMET C1206C332JCGACAUTO 3.3 nF 500 V C0G) or a film capacitor; schematic/PCB change required'),
    'C3,C10,C20,C2': ('CL10B103KB8NNNC', 'Samsung Electro-Mechanics', '1276-1009-1-ND', 5504, 0.10, 0.030, '10 nF 50 V X7R 0603'),
    'C4,C5': ('CL10C680JB8NNNC', 'Samsung Electro-Mechanics', '1276-1135-1-ND', 207000, 0.11, 0.044, '68 pF 50 V C0G 0603'),
    'C9': ('', '', '', '', 0, 0, 'UNSOURCED: schematic value is "C" (no capacitance given) - set the value first'),
    'C11,C23,C7,C21': ('C0603C104K5RACTU', 'KEMET', '399-C0603C104K5RACTUCT-ND', 2485421, 0.14, 0.077, '100 nF 50 V X7R 0603 (Samsung CL10B104KB8NNNC is on 61-week backorder)'),
    'C13,C33,C22': ('CL10C100JB8NNNC', 'Samsung Electro-Mechanics', '1276-1027-1-ND', 206747, 0.10, 0.037, '10 pF 50 V C0G 0603'),
    'C14': ('GRM1885C1H272JA01D', 'Murata Electronics', '490-3283-1-ND', 293979, 0.13, 0.070, '2.7 nF 50 V C0G 0603'),
    'C15': ('CC0603KRX7R8BB184', 'YAGEO', '13-CC0603KRX7R8BB184CT-ND', 19322, 0.20, 0.111, '180 nF 25 V X7R 0603 (no 50 V 0.18 uF 0603 stocked; node is 5 V)'),
    'C19,C27': ('UPW2A471MHD', 'Nichicon', '493-1985-ND', 5222, 2.73, 1.811, '470 uF 100 V substituted for 500 uF; 16 mm dia, 7.5 mm pitch, 31.5 mm tall; '
                'ripple 1.31 A @100 kHz; status Not-For-New-Designs (Panasonic EEU-FC2A471 is obsolete)'),
    'C32,C24,C31': ('CL10C101JB8NNNC', 'Samsung Electro-Mechanics', '1276-1008-1-ND', 1155305, 0.10, 0.033, '100 pF 50 V C0G 0603'),
    'C38,C26,C39': ('GRM188Z71E225KE43D', 'Murata Electronics', '490-GRM188Z71E225KE43DCT-ND', 147724, 0.18, 0.101, '2.2 uF 25 V 0603 (DigiKey lists X7R; Murata "Z7" code is X7T class)'),
    'C40,C16,C36,C6,C17,C8,C49,C52,C18,C53,C62,C61,C25,C48,C12': ('UMK107AB7105KA-T', 'Taiyo Yuden', '587-3247-1-ND', 579237, 0.20, 0.117, '1 uF 50 V X7R 0603'),
    'C47': ('C1206C105K1RACTU', 'KEMET', '399-C1206C105K1RACTUCT-ND', 31698, 0.81, 0.503, '1 uF 100 V X7R 1206 (Murata GRM31CR72A105KA01L backordered to Feb 2027). '
            'Also in the 11 A tank path - same cap-bank concern as C1/C58'),
    'C54,C28,C30,C29': ('GRJ31CZ72A475KE01L', 'Murata Electronics', '490-GRJ31CZ72A475KE01LCT-ND', 66536, 0.84, 0.529, '4.7 uF 100 V X7R 1206 soft-termination (GRM31CR72A475KE11L not stocked)'),
    'D2,D1': ('BAT46W', 'Diotec Semiconductor', '4878-BAT46WCT-ND', 83359, 0.19, 0.115, 'SOD-123 part on the SOD-123F footprint (pad pitch compatible). Vishay BAT46W-E3-08 backordered to Jan 2027'),
    'D3,D4': ('LTST-C190GKT', 'Lite-On Inc.', '160-LTST-C190GKTCT-ND', 1187734, 0.14, 0.094, 'green 0603 LED'),
    'D6,D5': ('MMSZ5231BT1G', 'onsemi', 'MMSZ5231BT1GOSCT-ND', 76458, 0.21, 0.128, '5.1 V 500 mW Zener SOD-123'),
    'IC2': ('LM2776DBVR', 'Texas Instruments', '296-43957-1-ND', 46809, 1.40, 1.018, ''),
    'IC3': ('OPA656UB/2K5', 'Texas Instruments', '296-OPA656UB/2K5CT-ND', 3184, 14.29, 11.27, 'schematic MPN field said ADA4817-1ARDZ-R7 (left over from the sample board) - corrected to the OPA656 the symbol and footprint describe'),
    'J1': ('XT60PW-M', 'AMASS', '', '', 0, 0, 'AMAZON: right-angle PCB-mount XT60 male; candidate listings B0DTGCK8VF (Gaslos, 90-degree XT60PW male/female) and B07VRLQ2C5 (Yiqigou, XT60PW pairs). '
           'Amazon blocks automated browsing - confirm the listing shows the XT60PW-M (male, PCB, 90 degree) before ordering'),
    'Q4,Q1,Q2,Q3': ('EPC2305', 'EPC', '917-EPC2305CT-ND', 15878, 8.81, 6.001, '150 V GaN FET'),
    'R1,R40,R41,R42': ('ERJ-3RQF3R3V', 'Panasonic Industry', 'P3.3AJCT-ND', 5604, 0.18, 0.091, '3.3 ohm substituted for 3.2 ohm (3.2 is not an E24/E96 value stocked in 0603)'),
    'R7': ('ERJ-3EKF6041V', 'Panasonic Industry', 'P6.04KHCT-ND', 36474, 0.10, 0.039, ''),
    'R8,R12': ('ERJ-3EKF1002V', 'Panasonic Industry', 'P10.0KHCT-ND', 621467, 0.10, 0.039, ''),
    'R10': ('ERJ-3GEY0R00V', 'Panasonic Industry', 'P0.0GCT-ND', 4415369, 0.10, 0.022, '0 ohm jumper'),
    'R11,R43,R44': ('ERJ-3EKF1001V', 'Panasonic Industry', 'P1.00KHCT-ND', 4055833, 0.10, 0.039, ''),
    'R13': ('ERJ-3EKF3302V', 'Panasonic Industry', 'P33.0KHCT-ND', 93742, 0.10, 0.039, ''),
    'R18': ('ERJ-3EKF3322V', 'Panasonic Industry', 'P33.2KHCT-ND', 89962, 0.10, 0.039, ''),
    'R19': ('ERJ-3EKF6811V', 'Panasonic Industry', 'P6.81KHCT-ND', 1074, 0.10, 0.039, 'DigiKey page is tagged Marketplace - may ship separately'),
    'R20,R22': ('ERJ-3EKF3301V', 'Panasonic Industry', 'P3.30KHCT-ND', 359068, 0.10, 0.039, ''),
    'R24,R51,R25,R47': ('ERJ-3EKF4701V', 'Panasonic Industry', 'P4.70KHCT-ND', 783994, 0.10, 0.039, ''),
    'R29,R28': ('ERJ-3EKF1502V', 'Panasonic Industry', 'P15.0KHCT-ND', 48445, 0.10, 0.039, ''),
    'R37,R4,R2,R6,R5,R3': ('ERJ-3EKF2202V', 'Panasonic Industry', 'P22.0KHCT-ND', 184599, 0.10, 0.039, ''),
    'R45,R46': ('ERJ-3EKF4703V', 'Panasonic Industry', 'P470KHCT-ND', 50008, 0.10, 0.039, ''),
    'ReceiverCoil1': ('0389690002', 'Molex', 'WM7469-ND', 4511, 2.59, 1.853, '2-circuit barrier terminal block, 12.7 mm pitch, PC-pin'),
    'S1_Gate_Driver1,U9,U1': ('SI8274GB1-IS1R', 'Skyworks Solutions Inc.', '336-5554-1-ND', 1683, 5.24, 4.529, ''),
    'U2': ('TLV3601DBVR', 'Texas Instruments', '296-TLV3601DBVRCT-ND', 5188, 5.31, 4.046, 'SOT-23-5 part; U2 footprint is TSOT-23-5 (same land pattern)'),
    'U3': ('TLV3601DBVR', 'Texas Instruments', '296-TLV3601DBVRCT-ND', 5188, 5.31, 4.046, ''),
    'U4': ('TPS7A2650DRVR', 'Texas Instruments', '296-TPS7A2650DRVRCT-ND', 5219, 1.32, 0.957, 'SUBSTITUTE for TPS7A2550DRVR (DigiKey backordered to May 2027). TPS7A26 fixed-5V WSON-6 is pin-identical '
           '(OUT/NC/PG/EN/GND/IN, checked in both datasheets), 500 mA, Vin 2.4-18 V, needs >=1 uF out (C26 = 2.2 uF)'),
    'U11,U10': ('SN74AHCT1G86DBVR', 'Texas Instruments', '296-4714-1-ND', 770, 0.14, 0.094, ''),
    'VCO1': ('SN74LV4046ADR', 'Texas Instruments', '296-21049-1-ND', 2768, 1.96, 1.446, 'cut-tape (DR) version of the SN74LV4046AD tube part; identical device'),
}
TP_NOTE = 'bare 2 mm PTH test pad - nothing to order'

rows = list(csv.DictReader(open('bom/bom.csv', newline='', encoding='utf8')))
hdr = list(rows[0].keys())
key = lambda refs: ','.join(sorted(r.strip() for r in refs.split(',')))
PK = {key(k): v for k, v in P.items()}
props, cost, unsourced = {}, [], []
for r in rows:
    k = key(r['Reference'])
    if r['Reference'].startswith('TP'):
        r['Notes'] = TP_NOTE; r['Chosen_Distributor'] = ''; r['Validated'] = 'n/a'; continue
    if k not in PK:
        print('no data for', r['Reference']); continue
    mpn, mfr, dk, stock, p1, p10, note = PK[k]
    r['MPN'], r['Manufacturer'], r['DigiKey'], r['DK_Stock'], r['Notes'] = mpn, mfr, dk, stock, note
    r['Chosen_Distributor'] = 'DigiKey' if dk else ('Amazon' if r['Reference'] == 'J1' else '')
    r['Validated'] = 'yes (digikey.com page 2026-11-09)' if dk else 'no'
    qty = int(r['Qty'])
    for ref in r['Reference'].split(','):
        ref = ref.strip(); d = {}
        if mpn: d['Manufacturer_Part_Number'] = mpn
        if mfr: d['Manufacturer_Name'] = mfr
        if dk: d['DigiKey_Part_Number'] = dk
        if note: d['BOM Comments'] = note
        if d: props[ref] = d
    if dk:
        unit = p10 if qty >= 10 else p1
        cost.append((r['Reference'], qty, dk, unit, qty * unit))
    else:
        unsourced.append(r['Reference'])
with open('bom/bom.csv', 'w', newline='', encoding='utf8') as f:
    w = csv.DictWriter(f, fieldnames=hdr); w.writeheader(); w.writerows(rows)
json.dump(props, open('bom/properties_update.json', 'w', encoding='utf8'), indent=1)
total = sum(c[4] for c in cost)
print(f'{"refs":34} {"qty":>3} {"DigiKey PN":30} {"unit":>7} {"ext":>7}')
for refs, qty, dk, unit, ext in sorted(cost, key=lambda c: -c[4]):
    print(f'{refs[:34]:34} {qty:3} {dk:30} {unit:7.2f} {ext:7.2f}')
print(f'DigiKey total for 1 board (qty-1 / qty-10 price tiers, no shipping/tax): ${total:.2f}')
print('unsourced:', unsourced)
print('properties for', len(props), 'symbols ->', 'bom/properties_update.json')

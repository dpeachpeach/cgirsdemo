"""Regenerate the synthetic golden pair in this directory.

Usage: python3 make_modest.py <scratch-clone-of-cgirsdemo>

Writes the synthetic records to <scratch>/data/MODEST.dat, runs the compiled
COBOL <scratch>/bin/FRZEVAL over them, and copies its MODFRZ.dat, FRZEVAL.rpt
and console output next to this script. The scratch clone must have been built
with ./tools/build.sh; the shipped repository tree is never modified.
"""
from decimal import Decimal


def pack(value, digits, scale, signed):
    q = Decimal(value).scaleb(scale).to_integral_value()
    neg = q < 0
    s = str(abs(int(q))).rjust(digits, '0')[-digits:]
    if signed:
        sign = 'D' if neg else 'C'
    else:
        sign = 'F'
    nib = s + sign
    if len(nib) % 2:
        nib = '0' + nib
    return bytes.fromhex(nib)


def rec(ein, mft, txpd, nctl, name, fsc, sic, frz,
        ased=2027105, rsed=2027105, csed=2034105,
        assd='0', dep='0', crd='0', pftd='0', pftf='0', pftp='0', intr='0',
        w8='        ', tccnt=0, fill=' ' * 16):
    out = b''
    out += f'{ein:09d}{mft:02d}{txpd:06d}'.encode()
    out += nctl.ljust(4)[:4].encode()
    out += name.ljust(35)[:35].encode()
    out += fsc.ljust(1)[:1].encode() + sic.ljust(1)[:1].encode()
    out += frz.ljust(8)[:8].encode()
    out += pack(ased, 7, 0, False) + pack(rsed, 7, 0, False) + pack(csed, 7, 0, False)
    out += pack(assd, 13, 2, True) + pack(dep, 13, 2, True) + pack(crd, 13, 2, True)
    out += pack(pftd, 11, 2, True) + pack(pftf, 11, 2, True) + pack(pftp, 11, 2, True)
    out += pack(intr, 11, 2, True)
    out += w8.ljust(8)[:8].encode()
    out += f'{tccnt:03d}'.encode()
    out += fill.ljust(16)[:16].encode()
    assert len(out) == 150, len(out)
    return out


CASES = [
    # id, description, kwargs
    ('S01', 'no freeze at all, positive balance',
     dict(ein=700000001, mft=1, txpd=202312, nctl='AAAA', name='SYN NO FREEZE', fsc='1', sic='0',
          frz='        ', assd='1000.00', dep='250.00', crd='100.00',
          pftd='10.00', pftf='20.00', pftp='30.00', intr='999.99')),
    ('S02', 'A freeze only', dict(ein=700000002, mft=1, txpd=202312, nctl='AAAA', name='SYN A', fsc='1', sic='0',
                                  frz='A       ', assd='500.00')),
    ('S03', 'V freeze only', dict(ein=700000003, mft=1, txpd=202312, nctl='AAAA', name='SYN V', fsc='1', sic='0',
                                  frz=' V      ', assd='500.00')),
    ('S04', 'L freeze only', dict(ein=700000004, mft=1, txpd=202312, nctl='AAAA', name='SYN L', fsc='1', sic='0',
                                  frz='  L     ', assd='500.00')),
    ('S05', 'S freeze only', dict(ein=700000005, mft=1, txpd=202312, nctl='AAAA', name='SYN S', fsc='1', sic='0',
                                  frz='    S   ', assd='500.00')),
    ('S06', 'Z freeze only', dict(ein=700000006, mft=1, txpd=202312, nctl='AAAA', name='SYN Z', fsc='1', sic='0',
                                  frz='      Z ', assd='500.00')),
    ('S07', 'X freeze only (never evaluated)',
     dict(ein=700000007, mft=1, txpd=202312, nctl='AAAA', name='SYN X', fsc='1', sic='0',
          frz='     X  ', assd='500.00')),
    ('S08', 'all five evaluated freezes set',
     dict(ein=700000008, mft=1, txpd=202312, nctl='AAAA', name='SYN ALL', fsc='1', sic='0',
          frz='AVL S Z ', assd='500.00')),
    ('S09', 'A and V together (refund and offset via distinct freezes)',
     dict(ein=700000009, mft=1, txpd=202312, nctl='AAAA', name='SYN AV', fsc='1', sic='0',
          frz='AV      ', assd='500.00')),
    ('S10', 'R and O already present in input, no evaluated freeze',
     dict(ein=700000010, mft=1, txpd=202312, nctl='AAAA', name='SYN RO PRESET', fsc='1', sic='0',
          frz='   R   O', assd='500.00')),
    ('S11', 'lowercase freeze letters do not match',
     dict(ein=700000011, mft=1, txpd=202312, nctl='AAAA', name='SYN LOWER', fsc='1', sic='0',
          frz='avl s z ', assd='500.00')),
    ('S12', 'negative balance (credit exceeds assessment)',
     dict(ein=700000012, mft=1, txpd=202312, nctl='AAAA', name='SYN NEG', fsc='1', sic='0',
          frz='    S   ', assd='100.00', crd='1000.50')),
    ('S13', 'balance exceeds the 9-digit report edit field',
     dict(ein=700000013, mft=1, txpd=202312, nctl='AAAA', name='SYN BIG', fsc='1', sic='0',
          frz='A       ', assd='12345678901.23')),
    ('S14', 'penalties drive the balance, deposits and credits subtract',
     dict(ein=700000014, mft=1, txpd=202312, nctl='AAAA', name='SYN MIX', fsc='1', sic='0',
          frz=' V      ', assd='1000.00', dep='300.33', crd='99.67',
          pftd='11.11', pftf='22.22', pftp='33.33', intr='5000.00')),
    ('S15', 'zero balance with L freeze',
     dict(ein=700000015, mft=1, txpd=202312, nctl='AAAA', name='SYN ZERO', fsc='1', sic='0',
          frz='  L     ', assd='0')),
    ('S16', 'large negative balance beyond the report edit field',
     dict(ein=700000016, mft=1, txpd=202312, nctl='AAAA', name='SYN BIGNEG', fsc='1', sic='0',
          frz='      Z ', crd='98765432109.87')),
    ('S17', 'A freeze with fractional cents rounding boundary',
     dict(ein=700000017, mft=1, txpd=202312, nctl='AAAA', name='SYN CENTS', fsc='1', sic='0',
          frz='A       ', assd='0.01', dep='0.02')),
    ('S18', 'L and Z together (both set refund and offset)',
     dict(ein=700000018, mft=1, txpd=202312, nctl='AAAA', name='SYN LZ', fsc='1', sic='0',
          frz='  L   Z ', assd='777.77')),
    ('S19', 'sum overflows the 11-digit whole part of the balance accumulator',
     dict(ein=700000019, mft=1, txpd=202312, nctl='AAAA', name='SYN OVERFLOW', fsc='1', sic='0',
          frz='A       ', assd='99999999999.99', pftd='999999999.99',
          pftf='999999999.99', pftp='999999999.99')),
    ('S20', 'balance exactly at the report edit field maximum',
     dict(ein=700000020, mft=1, txpd=202312, nctl='AAAA', name='SYN EDGE', fsc='1', sic='0',
          frz=' V      ', assd='999999999.99')),
]

if __name__ == '__main__':
    import shutil, subprocess, os, sys
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(sys.argv[1])
    data = b''.join(rec(**kw) for _, _, kw in CASES)
    with open(os.path.join(root, 'data/MODEST.dat'), 'wb') as f:
        f.write(data)
    env = dict(os.environ, COB_LIBRARY_PATH=os.path.join(root, 'bin'))
    stdout = subprocess.run(['bin/FRZEVAL'], cwd=root, env=env, capture_output=True, text=True).stdout
    print(stdout)
    open(os.path.join(root, 'data/FRZEVAL.stdout'), 'w').write(stdout)
    out = open(os.path.join(root, 'data/MODFRZ.dat'), 'rb').read()
    rpt = open(os.path.join(root, 'data/FRZEVAL.rpt')).read()
    outrecs = [out[i:i + 150] for i in range(0, len(out), 150)]
    for (cid, desc, _), i, o in zip(CASES, [data[i:i + 150] for i in range(0, len(data), 150)], outrecs):
        print(cid, desc, '| in frz=%r out frz=%r' % (i[58:66].decode(), o[58:66].decode()),
              '| rest-identical=', i[:58] == o[:58] and i[66:] == o[66:])
    print('--- REPORT ---')
    print(rpt)
    for name in ('MODEST.dat', 'MODFRZ.dat', 'FRZEVAL.rpt', 'FRZEVAL.stdout'):
        shutil.copy(os.path.join(root, 'data', name), os.path.join(here, name))

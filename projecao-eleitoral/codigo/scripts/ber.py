"""Parser BER mínimo, sem especificação ASN.1."""
def parse(b, i=0, end=None):
    end = len(b) if end is None else end
    out = []
    while i < end:
        t = b[i]; i += 1
        cls, cons, num = t >> 6, bool(t & 0x20), t & 0x1f
        if num == 0x1f:
            num = 0
            while True:
                x = b[i]; i += 1; num = (num << 7) | (x & 0x7f)
                if not x & 0x80: break
        l = b[i]; i += 1
        if l & 0x80:
            n = l & 0x7f; l = int.from_bytes(b[i:i+n], 'big'); i += n
        v = b[i:i+l]
        node = {'cls': cls, 'tag': num, 'cons': cons}
        if cons: node['kids'] = parse(b, i, i+l)
        else: node['val'] = v
        out.append(node); i += l
    return out

def dump(nodes, d=0, maxd=20):
    for n in nodes:
        lab = f"{'  '*d}[{'UAPC'[n['cls']]}{n['tag']}]"
        if n['cons']:
            print(lab, f"({len(n['kids'])})"); 
            if d < maxd: dump(n['kids'], d+1, maxd)
        else:
            v = n['val']
            s = v.decode('latin1') if v and all(32 <= c < 127 or c > 159 for c in v) else (str(int.from_bytes(v,'big',signed=True)) if len(v) <= 8 else v[:12].hex()+'…')
            print(lab, s)

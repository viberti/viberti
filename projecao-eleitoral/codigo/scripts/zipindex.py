"""Lê o diretório central de um zip remoto via HTTP Range (sem baixar o arquivo). Suporta ZIP64.
Uso: python3 -I zipindex.py <url> <saida.csv>"""
import sys, struct, requests, csv
url, out = sys.argv[1], sys.argv[2]
s = requests.Session()
size = int(s.head(url, timeout=60).headers["Content-Length"])
def rng(a, b): return s.get(url, headers={"Range": f"bytes={a}-{b}"}, timeout=300).content
tail = rng(max(0, size - 65600), size - 1)
i = tail.rfind(b"PK\x05\x06")
cd_size, cd_off = struct.unpack("<II", tail[i+12:i+20])
j = tail.rfind(b"PK\x06\x06")
if j >= 0:   # ZIP64 end record
    cd_size, cd_off = struct.unpack("<QQ", tail[j+40:j+56])
cd = rng(cd_off, cd_off + cd_size - 1)
p = 0; rows = []
while p < len(cd) and cd[p:p+4] == b"PK\x01\x02":
    (mtime, mdate) = struct.unpack("<HH", cd[p+12:p+16])
    csz, usz = struct.unpack("<II", cd[p+20:p+28])
    nl, el, cl = struct.unpack("<HHH", cd[p+28:p+34])
    name = cd[p+46:p+46+nl].decode("latin1")
    y = 1980 + (mdate >> 9); mo = (mdate >> 5) & 15; d = mdate & 31
    h = mtime >> 11; mi = (mtime >> 5) & 63; se = (mtime & 31) * 2
    rows.append((name, f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{se:02d}", usz))
    p += 46 + nl + el + cl
csv.writer(open(out, "w")).writerows(rows)
print(len(rows), "entradas; tamanho do zip", size)

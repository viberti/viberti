"""Confere o SHA-256 de cada arquivo listado nos protocolos congelados contra a pasta codigo/.
Uso: python3 verificar_hashes.py [protocolo_v1.json protocolo_v2.json]"""
import hashlib, json, os, sys
base = os.path.dirname(os.path.abspath(__file__))
bad = 0
for prot in sys.argv[1:] or ["protocolo_v1.json", "protocolo_v2.json"]:
    p = json.load(open(os.path.join(base, prot)))
    print("==", prot)
    for path, h in p["codigo_sha256"].items():
        f = os.path.join(base, "codigo", path)
        got = hashlib.sha256(open(f, "rb").read()).hexdigest() if os.path.exists(f) else "AUSENTE"
        print(("OK      " if got == h else "DIFERE  ") + path); bad += got != h
sys.exit(1 if bad else 0)

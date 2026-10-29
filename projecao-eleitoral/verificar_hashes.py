"""Confere o SHA-256 de cada arquivo listado no protocolo congelado contra a pasta codigo/."""
import hashlib, json, os, sys
base = os.path.dirname(os.path.abspath(__file__))
p = json.load(open(os.path.join(base, "protocolo_v1.json")))
bad = 0
for path, h in p["codigo_sha256"].items():
    f = os.path.join(base, "codigo", path)
    got = hashlib.sha256(open(f, "rb").read()).hexdigest() if os.path.exists(f) else "AUSENTE"
    print(("OK      " if got == h else "DIFERE  ") + path); bad += got != h
sys.exit(1 if bad else 0)

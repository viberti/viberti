"""Teste de vazamento: a projeção num corte não pode depender dos votos das seções ainda não apuradas.
Roda o modelo num corte, embaralha os votos do turno-alvo (v22, v13, val2 e y) entre as seções não apuradas
e confere que projeção, faixa e sinais do semáforo ficam idênticos.
Uso: ANO=2026 UNC=bv SIMS=50 python3 -I testes/teste_vazamento.py tse_2026.duckdb
"""
import os, sys, numpy as np, pandas as pd
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp = sys.argv[1]; sys.argv = ["modelo.py", dbp, "/tmp/teste_vazamento"]
exec(src)
ok = True
for frac, seed in ((0.005, 1), (0.05, 2), (0.30, 3)):
    o = np.random.default_rng(seed).permutation(N)
    rep = pd.Series(o < frac * N, index=b.index)
    r1 = project(rep, sims=50, rng=np.random.default_rng(0))
    b0 = b.copy()
    u = ~rep.values; idx = np.where(u)[0]; perm = np.random.default_rng(99).permutation(idx)
    for col in ("v22", "v13", "val2", "y"):
        vals = b[col].values.copy(); vals[idx] = vals[perm]; b[col] = vals
    r2 = project(rep, sims=50, rng=np.random.default_rng(0))
    b = b0
    same = all(np.isclose(r1[k], r2[k], atol=1e-12) for k in ("modelo", "lo", "hi"))
    print(f"corte {frac:.1%}: projeção {100*r1['modelo']:.4f} vs {100*r2['modelo']:.4f}; faixa {100*r1['lo']:.4f}–{100*r1['hi']:.4f} vs {100*r2['lo']:.4f}–{100*r2['hi']:.4f} -> {'OK' if same else 'FALHOU'}")
    ok &= same
print("SEM VAZAMENTO" if ok else "VAZAMENTO DETECTADO"); sys.exit(0 if ok else 1)

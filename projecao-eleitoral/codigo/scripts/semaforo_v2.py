"""Regras do semáforo do protocolo v2 aplicadas a um ou mais semaforo_pontos.csv (saída de semaforo.py).
Diferença em relação ao v1: o verde só pode acender com >= 15% das seções apuradas. Os parâmetros do modelo
do v2 (TAU_UF_MIN=0,15, COV=1x, TIPO=1) entram na geração dos pontos (run_v2b.sh), não aqui.
Uso: python3 -I semaforo_v2.py <csv> [<csv> ...]   → imprime o resumo e grava luzes_v2.csv ao lado do primeiro csv
"""
import os, sys, numpy as np, pandas as pd

ALARME = 0.15          # |correlação dentro do município| que força vermelho
VERDE_MIN_SECOES = 0.15
VERDE_COB_CELULA = 0.01
VIES_MAX = 10
AMARELO_DIST = 1.0
AMARELO_MUN = 200


def luzes(d):
    d = d.sort_values(["fonte", "ordem", "pct_secoes"]).copy()
    alarme = d.corr_intra.abs().fillna(0) >= ALARME
    vies_ok = d.vies_hist_pp.abs() <= VIES_MAX
    verde = (d.pct_secoes >= VERDE_MIN_SECOES - 1e-9) & (d.cob_min_tipo_regiao >= VERDE_COB_CELULA) & vies_ok & ~alarme
    amarelo = (d.n_mun >= AMARELO_MUN) & vies_ok & ((d.modelo - 50).abs() >= AMARELO_DIST) & ~alarme
    # uma vez verde, o vencedor fica anunciado enquanto a faixa de 90% não contiver 50
    ja_verde = verde.groupby([d.fonte, d.ordem]).cummax()
    fora50 = (d.lo > 50) | (d.hi < 50)
    amarelo = amarelo | (ja_verde & fora50 & ~alarme)
    d["luz"] = np.where(alarme, "vermelho", np.where(verde, "verde", np.where(amarelo, "amarelo", "vermelho")))
    return d


if __name__ == "__main__":
    d = pd.concat([pd.read_csv(f).assign(fonte=os.path.basename(os.path.dirname(f))) for f in sys.argv[1:]], ignore_index=True)
    d = luzes(d)
    d["ae"] = (d.modelo - d.verdade).abs()
    v = d[d.luz == "verde"]; a = d[d.luz.isin(["verde", "amarelo"])]
    errado = np.sign(a.modelo - 50) != np.sign(a.verdade - 50)
    print(f"pontos {len(d)} | verdes {len(v)} | verde com erro <= 0,5: {100 * (v.ae <= 0.5).mean():.1f}% | erro máx verde {v.ae.max():.2f}")
    print(f"vencedor anunciado (amarelo ou verde) em {len(a)} pontos, errado em {int(errado.sum())}")
    prim = v.groupby(["fonte", "ordem"]).pct_secoes.min()
    print(f"ordens com verde {len(prim)} de {d.groupby(['fonte', 'ordem']).ngroups} | primeiro verde, mediana {100 * prim.median():.0f}% das seções")
    d.to_csv(os.path.join(os.path.dirname(sys.argv[1]), "luzes_v2.csv"), index=False)

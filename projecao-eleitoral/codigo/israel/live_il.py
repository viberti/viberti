"""Leitor ao vivo da contagem da Knesset 26 (CEC) + projeção de cadeiras.
Uso: python3 -I live_il.py <saida_dir> [arquivo_local.csv]   (com arquivo local: roda uma vez, para teste)
Sem arquivo: procura o expb.csv nos endereços prováveis a cada 3 min e grava snapshot.json, historico.csv, painel.html.
"""
import os, sys, io, json, time, datetime as dt, warnings, requests, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/claude/israel")
from modelo_il import *
import painel

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
LOCAL = sys.argv[2] if len(sys.argv) > 2 else None
URLS = ["https://raw.githubusercontent.com/OmerCohenBI/k26-turnout-live/main/k26_expb.csv", "https://cdn-votes26.bechirot.gov.il/files/expb.csv", "https://cdn-media26.bechirot.gov.il/files/expb.csv", "https://media26.bechirot.gov.il/files/expb.csv", "https://votes26.bechirot.gov.il/files/expb.csv",
        "https://votes26.bechirot.gov.il/expb.csv", "https://media26.bechirot.gov.il/expb.csv"]
NOMES = {"ני": "Noam", "מחל": "Likud", "רק": "Juntos (Bennett)", "דרך": "Yashar (Eisenkot)", "אמת": "Democratas", "ל": "Yisrael Beiteinu",
         "ב": "Otzma Yehudit", "ט": "Sionismo Religioso", "שס": "Shas", "ג": "Judaísmo da Torá", "עם": "Ra'am",
         "ודם": "Lista Conjunta", "כן": "Azul e Branco", "ך": "Amcha Yisrael (Winter)", "די": "Reservistas (Hendel)",
         "זך": "Público Haredi", "_outros": "Outros"}
# histórico 2022 (Knesset 25) como proxy geográfico de cada lista de 2026
MAP_REF = {"מחל": {"מחל": 1}, "רק": {"פה": 1, "ב": 1}, "דרך": {"כן": 1}, "אמת": {"אמת": 1, "מרצ": 1}, "ל": {"ל": 1},
           "ב": {"ט": 1}, "ט": {"ט": 1}, "שס": {"שס": 1}, "ג": {"ג": 1}, "עם": {"עם": 1}, "ודם": {"ום": 1, "ד": 1},
           "כן": {"כן": 1}, "ך": {"ט": 1, "מחל": 1}, "די": {"כן": 1, "ל": 1}, "זך": {"ג": 1}, "ני": {"ט": 1}}
AG = [("רק", "ל"), ("דרך", "אמת"), ("ודם", "עם"), ("מחל", "ט"), ("שס", "ג")]
BLOCO = ["מחל", "ב", "ט", "שס", "ג"]                 # coalizão de Netanyahu
ENVELOPES = 640000                                  # válidos esperados nos envelopes duplos (CEC: >650 mil envelopes; ~2% inválidos)

ref, rp = load_kalpi("/home/claude/israel/k25_expb.csv")
P = Projetor(ref, rp, MAP_REF, growth=1.08, tau=(0.30, 0.25, 0.30), tau_g=0.05)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica)"

def fetch():
    for u in URLS:
        try:
            r = S.get(u, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000: return u, r.content
        except Exception: pass
    return None, None

def parse(raw):
    for enc in ("utf-8-sig", "cp1255"):
        try:
            txt = raw.decode(enc); p = os.path.join(OUT, "ultimo_expb.csv"); open(p, "w", encoding="utf-8-sig").write(txt)
            return load_kalpi(p)
        except UnicodeDecodeError: continue
    raise ValueError("encoding")

def leitura(cur, cp):
    sec = cur.city_id.map(P.sec_city).fillna("geral")
    exp_sec = P.u.groupby("sector").valid.sum() * 1.08
    cob = (cur[cur.city_id != ENV].groupby(sec).valid.sum() / exp_sec).fillna(0)
    tot = cur[cur.city_id != ENV].valid.sum() / (P.u.valid.sum() * 1.08)
    if tot >= 0.10 and cob.min() >= 0.05: luz = "verde"
    elif tot >= 0.03 and cob.get("geral", 0) >= 0.03: luz = "amarelo"
    else: luz = "vermelho"
    return luz, {k: round(float(v), 3) for k, v in cob.items()}, float(tot)

def roda(raw, fonte):
    cur, cp = parse(raw)
    cur = cur.rename(columns={"עמ": "עם", "ודעם": "ודם"}); cp = [{"עמ": "עם", "ודעם": "ודם"}.get(c, c) for c in cp]
    cur = cur[cur.valid > 0]
    novas = [c for c in cp if c not in MAP_REF and cur[c].sum() > 0.005 * cur.valid.sum()]
    mapcur = {t: {t: 1} for t in MAP_REF}
    out, info = P.project(cur, mapcur, cp, sims=400, agreements=AG, coalition=BLOCO, envelopes=ENVELOPES)
    luz, cob, tot = leitura(cur, cp)
    parcial = group(cur, mapcur, cp).sum(); parcial = 100 * parcial / parcial.sum()
    out["parcial"] = parcial.reindex(out.index); out["nome"] = [NOMES.get(i, i) for i in out.index]
    out = out.sort_values("pct_proj", ascending=False)
    t = dt.datetime.now(dt.timezone.utc)
    snap = dict(hora_utc=t.isoformat(timespec="seconds"), fonte=fonte, luz=luz, cobertura_setor=cob,
                pct_votos_regulares=round(tot, 3), letras_sem_mapa=novas, **{k: v for k, v in info.items()},
                listas=out.reset_index(names="letra").round(3).to_dict("records"))
    json.dump(snap, open(os.path.join(OUT, "snapshot.json"), "w"), ensure_ascii=False, indent=1, default=float)
    h = os.path.join(OUT, "historico.csv")
    row = pd.DataFrame([dict(hora_utc=snap["hora_utc"], urnas=len(cur), pct=tot, luz=luz, p61=info["p61"], bloco=info["coal_ponto"],
                             bloco_lo=info["coal_lo"], bloco_hi=info["coal_hi"], **{f"cad_{k}": v for k, v in out.cad_ponto.items()},
                             **{f"pct_{k}": v for k, v in out.pct_proj.items()})])
    row.to_csv(h, mode="a", header=not os.path.exists(h), index=False)
    print(snap["hora_utc"], "urnas", len(cur), f"{100*tot:.1f}%", luz, "bloco", info["coal_ponto"],
          f'({info["coal_lo"]:.0f}-{info["coal_hi"]:.0f}) P(61+)={info["p61"]:.2f}', "sem mapa:", novas, flush=True)
    open(os.path.join(OUT, "painel.html"), "w").write(painel.gera(OUT))
    import subprocess; subprocess.run([sys.executable, "-I", "/home/claude/israel/export_dash.py", OUT])
    print(out[["nome", "parcial", "pct_proj", "pct_lo", "pct_hi", "cad_ponto", "cad_lo", "cad_hi", "p_barreira"]].round(2).to_string(), flush=True)

if LOCAL:
    roda(open(LOCAL, "rb").read(), LOCAL); sys.exit()
last = None
while True:
    u, raw = fetch()
    if raw is not None and raw != last:
        try: roda(raw, u); last = raw
        except Exception as e: print("erro", repr(e), flush=True)
    elif raw is None: print(dt.datetime.now().strftime("%H:%M:%S"), "ainda sem arquivo", flush=True)
    time.sleep(180)

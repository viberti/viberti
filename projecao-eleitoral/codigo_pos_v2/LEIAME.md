# Código posterior ao protocolo v2

Esta pasta não faz parte de nenhum protocolo congelado; os arquivos em `codigo/` continuam idênticos aos hashes de `protocolo_v1.json` e `protocolo_v2.json`.

`scripts/modelo.py` aqui é o modelo dos protocolos com opções novas, todas desligadas por padrão (com elas desligadas, o resultado é o mesmo do código congelado):

| Variável | O que faz | Resultado |
|---|---|---|
| `GOV_UF=<UF>` | 2º turno de governador numa UF (banco de `load_gov.py`, `load_gov_uf.py`, `load_gov_2026.py`) | Teste fora da amostra, ver `gov_analise.txt` |
| `MUNVIZ=1` (`MUNVIZ_H`, `MUNVIZ_K`, `MUNVIZ_N`) | Efeito do município previsto pelos vizinhos já apurados (núcleo gaussiano) | Rejeitado |
| `FEAT=reg` com `REGH` | Coeficientes por região encolhidos para o nacional | Rejeitado |
| `TAU_UF_S0`, `TAU_UF_NU` | Hiperprior qui-quadrado inverso escalado para τ_UF | Rejeitado |

Governador: `scripts/gov_run.sh 2022 2026` e depois `scripts/gov_analise.py`. Os caminhos continuam absolutos da máquina original.

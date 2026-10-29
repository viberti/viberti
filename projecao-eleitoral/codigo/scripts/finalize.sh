#!/bin/bash
# Depois dos downloads: decodifica BU, monta eleitores, roda o replay do modelo no dado nacional de 2026.
set -e
cd /home/claude/tse
python3 -I scripts/decode_bu.py bu2t/bu.sqlite tse_2022_2026.duckdb
python3 -I scripts/build_eleitores.py bu2t tse_2022_2026.duckdb
ANO=2026 TAU_G=0.02 TAU_UF_MIN=0.027 python3 -I scripts/modelo.py tse_2022_2026.duckdb modelo/2026_proxy > modelo/2026_proxy.log 2>&1
echo FINALIZADO

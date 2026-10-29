#!/bin/bash
# candidata v3c: v2b + coeficientes regionais encolhidos (FEAT=reg, REGH=1) + hiperprior de τ_UF (S0 deixando a eleição de fora, NU=5) no lugar do piso 0,15
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0 COV=1x TIPO=1 FEAT=reg REGH=1 TAU_UF_MIN=0.027 TAU_UF_NU=5
export ORDENS=real,aleatoria_0,aleatoria_1,aleatoria_2,realista_0,realista_1,realista_2,realista_3,realista_4,NE_primeiro,S_primeiro,capitais_primeiro,pro22_primeiro
db() { case $1 in 2006|2010|2014) echo tse_hist.duckdb;; 2018) echo tse_1418.duckdb;; 2022) echo tse_2022_2026.duckdb;; 2026) echo tse_2026.duckdb;; esac; }
s0() { case $1 in 2006) echo 0.145;; 2010) echo 0.1434;; 2014) echo 0.0954;; 2018) echo 0.1255;; 2022) echo 0.1481;; 2026) echo 0.1478;; esac; }
job() { ano=$1; ordem=$2; nome=$3; only=$4; out=modelo/sem_v3c/${ano}_$nome; mkdir -p modelo/sem_v3c
  ( export ANO=$ano ORDEM_REAL=$ordem TAU_UF_S0=$(s0 $ano); [ "$only" = 1 ] && export ORDENS=real; python3 -I scripts/semaforo.py $(db $ano) $out ) > $out.log 2>&1; echo "$ano $nome fim $(date +%T)"; }
export -f job db s0
{
for a in 2006 2010 2014 2018; do echo "$a hist/ordem_${a}_com_2022_2t.csv todas 0"; echo "$a hist/ordem_${a}_com_2026_2t.csv real2026_2t 1"; done
echo "2022 hist/ordem_real_2022_2t.csv todas 0"; echo "2026 hist/ordem_real_2026_2t.csv todas 0"
} | xargs -P 3 -L 1 bash -c 'job $0 $1 $2 $3'
echo V3C_OK

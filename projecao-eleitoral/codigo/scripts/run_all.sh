#!/bin/bash
# BU (12 ligações) e logs/RDV (12 ligações) em paralelo, ritmo moderado para não acionar o 429
cd /home/claude/tse
( python3 -I scripts/crawl_bu.py bu2t 12 >> bu2t/crawl.log 2>&1
  echo "=== segunda passagem" >> bu2t/crawl.log
  python3 -I scripts/crawl_bu.py bu2t 8 >> bu2t/crawl.log 2>&1 ) &
sleep 20
python3 -I scripts/crawl_log_rdv.py bu2t 12 >> bu2t/logrdv.log 2>&1
wait
echo "TUDO TERMINADO" >> bu2t/crawl.log

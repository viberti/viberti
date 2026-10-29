#!/bin/bash
# duas passagens: a segunda refaz só as falhas transitórias
cd /home/claude/tse
python3 -I scripts/crawl_bu.py /home/claude/tse/bu2t 32 >> bu2t/crawl.log 2>&1
echo "=== segunda passagem" >> bu2t/crawl.log
python3 -I scripts/crawl_bu.py /home/claude/tse/bu2t 16 >> bu2t/crawl.log 2>&1

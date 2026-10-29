# Ordens reais de chegada

Uma linha por seção: `sg_uf, cd_municipio, nr_zona, nr_secao, t_real` (código de município do TSE; hora de Brasília).

| Arquivo | Noite | Fonte da hora | Seções |
|---|---|---|---|
| `ordem_real_2022_2t.csv.gz` | 2º turno, 30/10/2022 | Data de gravação de cada BU no diretório central dos ZIPs de arquivos transmitidos, por UF | 471.984 |
| `ordem_real_2026_2t.csv.gz` | 2º turno, 25/10/2026 | Idem; hora local convertida para Brasília com o fuso de cada município, inferido da hora de abertura das urnas; seções do exterior postas entre 17h01 e 17h03 | 499.178 |
| `ordem_real_2026_1t.csv.gz` | 1º turno, 04/10/2026 | Hora de recebimento no arquivo auxiliar de cada seção (campos dr e hr do aux.json, pleito 3220) | 499.207 |

Observações:
- No 1º turno, a hora dos arquivos transmitidos é a de empacotamento, não a de chegada; por isso o 1º turno de 2022 não tem ordem real.
- No 2º turno de 2026 a votação foi prorrogada até as 19h e o TSE suspendeu a divulgação até esse horário; a ordem reflete a chegada dos arquivos, não a divulgação.
- 17 seções do 2º turno de 2026 (AM, PA, PE) têm hora anterior às 17h, provavelmente por erro na inferência do fuso ou por encerramento antecipado.

# Ordens reais transplantadas para eleições sem ordem de chegada

Não há hora de chegada por seção publicada para 2006, 2010, 2014 e 2018. Para testar o modelo numa noite com o padrão real de chegada, a hora de cada seção numa noite real (2º turno de 2022 ou de 2026) foi atribuída à mesma seção (UF, município, zona, seção) da eleição antiga. As seções sem correspondência receberam uma hora sorteada entre as horas das seções casadas do mesmo município.

| Arquivo | Eleição | Noite de origem | Seções | Casadas pela seção |
|---|---|---|---|---|
| `ordem_2006_com_2022_2t.csv.gz`, `ordem_2006_com_2026_2t.csv.gz` | 2º turno 2006 | 2022, 2026 | 361.406 | 75% |
| `ordem_2010_com_2022_2t.csv.gz`, `ordem_2010_com_2026_2t.csv.gz` | 2º turno 2010 | 2022, 2026 | 399.962 | 78% |
| `ordem_2014_com_2022_2t.csv.gz`, `ordem_2014_com_2026_2t.csv.gz` | 2º turno 2014 | 2022, 2026 | 428.852 | 80% |
| `ordem_2018_com_2022_2t.csv.gz`, `ordem_2018_com_2026_2t.csv.gz` | 2º turno 2018 | 2022, 2026 | 454.490 | 96% |

Observações:
- O código municipal é o do TSE; a hora é a da noite de origem (Brasília).
- Os arquivos de trabalho de 2018 usados nas rodadas tinham a hora numa escala errada (dividida por 1000); a ordem das seções era a mesma. Os arquivos aqui têm a hora corrigida, e a ordem foi conferida contra os de trabalho.
- Uma ordem transplantada conserva o calendário real de UFs, municípios e zonas, mas não o que fazia uma seção chegar antes de outra naquela eleição (urnas, transmissão, apuração no cartório). É um teste intermediário entre as ordens simuladas e uma ordem real.

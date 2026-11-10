# Portal da Dança — Análise, revisão dos fluxogramas e implementação

Versão 1.0 (10/11/2026). A seção 2 descreve os problemas dos fluxogramas da versão preliminar, já corrigidos em `docs/fluxogramas/` (numerados de 00 a 17). Relatório final: `docs/relatorio/Relatorio_Portal_da_Danca_v1.0.docx` (e `.pdf`).

## 1. Observações da professora (versão anotada) e como foram tratadas

| # | Observação / destaque | Situação na versão revisada | Implementação |
|---|---|---|---|
| 1 | Comentário após RF16: *"adicionar ou remover aulas e horários, cadastro de professores, quantidade de alunos por aula, etc."* | Atendido com RF17–RF21 | `professores`, `aulas` (Turma, Modalidade, Sala, vínculo) |
| 2 | Comentário após RN07: *regras para os alunos — matrícula, pagamento em dia, tolerância, taxa de matrícula, afastamento, exame médico* | Atendido com RN08 (escola **não** adota essas regras) | Sistema nunca bloqueia presença por pagamento; aluno avulso na chamada; status da mensalidade só informativo |
| 3 | RF05 "Controle de entrada e saída de alunos" destacado (escola não tem catraca) | Substituído por "Consulta da agenda de aulas"; 3.2 explica a ausência de catraca | `aulas:agenda` com filtros |
| 4 | RF08/RN02 misturavam forma de pagamento e origem | Separado: forma (Pix/dinheiro/cartão) **e** origem | Campos `forma_pagamento` e `origem`, ambos obrigatórios em entradas |
| 5 | RF13 "Controle de salários" — como é calculado? | Por aluno inscrito na matrícula (RF13, RN07, RN16) | `financeiro.services.calcular_salario` = inscrições ativas no mês × valor por aluno |
| 6 | RF10/RN04 "validade" | "quando aplicável" | `validade` opcional, nunca anterior ao pagamento |
| 7 | 3.1 descrição da empresa / 3.3 objetivos destacados | Ampliados (250 alunos, 2 salas × 40, 18h–22h, modalidades) | Migração inicial cria salas e modalidades; agenda valida 18h–22h |
| 8 | RNF06–RNF08 destacados (genéricos) | Mantidos como transversais | Contraste/foco/labels (RNF06), login obrigatório (RNF03), SQLite persistente (RNF08) |

**Pendências ainda abertas no relatório (sugestão de ajuste):**
- RF13/RN07 não informam o **valor** pago por aluno inscrito → o sistema deixa configurável por professor (`valor_por_aluno`). Confirmar com a escola.
- Não há requisito de **edição/exclusão de lançamentos financeiros** (correção de erro de digitação). Foi implementado; sugerimos incluir no relatório (apoia RNF05).
- Não há requisito/fluxo de **login** (RNF03 o pressupõe). Sugerimos um fluxo "00 – Acesso ao sistema".

## 2. Revisão dos fluxogramas

| Fluxo | Problema encontrado | Correção sugerida |
|---|---|---|
| 01 Alunos | A seta de "Solicitar correção dos dados" vai para **"Cadastrar aluno"** — dados inválidos acabam cadastrados. | Ligar "Solicitar correção" de volta a "Informar dados do aluno". |
| 02 Professores | Seta "Não: revisar" é bidirecional entre a entrada e o losango (ambíguo). | Seta única do losango (Não) para "Informar dados do professor". |
| 03 Aulas | "Selecionar operação" está como **paralelogramo** mas ramifica; "Não" com seta dupla. | Usar losango de decisão; laço explícito. |
| 04 Agendamento | (a) Não verifica **conflito de sala/horário** nem de professor; (b) ramo "Não" (> 40) termina em Fim sem salvar e sem voltar; (c) "Quantidade prevista" é entrada → paralelogramo; (d) não cobre atualizar/remover agendamento nem atualizar vínculo (RF19/RF21). | Adicionar decisão "Sala e professor livres no horário?"; ramo "Não" volta para revisar; incluir ramos atualizar/remover. |
| 06 Presença | Não prevê **aluno não vinculado** (RN08: sem matrícula obrigatória). | Incluir "Adicionar aluno avulso à chamada". |
| 08 Entradas | "Selecionar forma de pagamento" é paralelogramo com 3 saídas (deveria ser losango); "Validar dados" não tem ramo de erro; origem "mensalidade" aqui duplica o fluxo 10 sem pedir o aluno. | Losango; ramo "dados inválidos → corrigir"; se origem = mensalidade, selecionar aluno. |
| 09 Saídas | Cálculo do salário está escondido dentro de "Selecionar categoria"; losango "Categoria corresponde a uma opção?" é redundante em lista fechada. | Subprocesso próprio (fluxo 11): professor → mês → contar inscrições → × valor por aluno → confirmar. |
| 10 Mensalidades | **Não pede forma de pagamento** (contraria RN02/RN12) nem **validade** (caso típico de RN04); registrar e consultar estão em sequência obrigatória. | Incluir forma e validade; decisão inicial "Registrar ou Consultar". |
| 13 Balanço | Soma antes de verificar se há movimentações. | Verificar primeiro (detalhe, não é erro). |
| Numeração | Rastreabilidade usa 01–04, 06, 08–10, 12–14: faltam 05, 07 e 11. | Renumerar ou explicar as lacunas. |

## 3. Rastreabilidade → código → testes

| Requisito | Onde está | Testes |
|---|---|---|
| RF01/RF02 | `alunos/views.py` | `alunos/tests.py` |
| RF03/RF04 | `aulas/views.py::chamada`, `presencas` | `aulas/tests.py::ChamadaViewTests` |
| RF05 | `aulas/views.py::agenda` | `AgendaViewTests` |
| RF06–RF10, RF12, RF14 | `financeiro/models.py`, `forms.py`, `views.py` | `financeiro/tests.py` |
| RF11/RN06 | `financeiro:mensalidades` | `FinanceiroViewTests`, `FormsTests` |
| RF13/RN07 | `financeiro/services.py::calcular_salario` | `SalarioTests` |
| RF15/RF16/RN05 | `calcular_saldo`, `balanco_mensal` | `SaldoBalancoTests` |
| RF17 | `professores/` | `professores/tests.py` |
| RF18/RF19/RN10 | `aulas/models.py::Turma.clean` | `TurmaRegrasTests`, `ModalidadeViewTests` |
| RF20/RF21/RN09 | `Turma.validar_quantidade`, `VinculoAlunosForm` | `CapacidadeTests` |
| RN01–RN04, RN12 | `Movimentacao.clean` | `MovimentacaoRegrasTests` |
| RN08 | chamada com avulso; mensalidade só informativa | `test_aluno_avulso_sem_matricula`, `test_aluno_sem_mensalidade_pode_ter_presenca` |
| RNF03/RNF04 | `LoginRequiredMiddleware`, CSRF, redirect seguro | `administradores/tests.py::SegurancaTests` |
| RNF05 | validações de modelo, `UniqueConstraint`, `PROTECT` | vários |
| RF25/RN17 | `consultas/services.py::consulta`, `IndicadorTurma` | `consultas/tests.py` |

## 4. Como rodar

```bash
cd project
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # se necessário
.venv/bin/python manage.py migrate
DJANGO_DEMO_SENHA='escolha-uma-senha' .venv/bin/python manage.py popular_demo   # usuário: responsavel
.venv/bin/python manage.py collectstatic --noinput   # arquivos de estilo
.venv/bin/python manage.py test                # suíte completa
sudo ufw allow 3010/tcp                        # liberar a porta no firewall
.venv/bin/python manage.py runserver 0.0.0.0:3010
```
Acesse `http://<ip-da-máquina>:3010/`. Depois de clonar o repositório, siga o passo a passo do Resumo ("Depois de clonar o repositório"): ele explica o que fica fora do git e como recriar.

## 5. Módulo Consultas — frequência e oportunidades de promoção

### 5.1 Requisitos

Os dois requisitos estão no relatório final (seção 4.5) e no fluxo 17.

| Código | Requisito |
|---|---|
| RF25 | Consulta de frequência e oportunidades: o proprietário vê, para um período (4, 8, 12 ou 26 semanas), as aulas mais frequentadas, a ocupação de cada aula e da agenda, e quais aulas são candidatas a promoção. |
| RN17 | A ocupação é medida pela presença, não pela inscrição: média de alunos presentes por aula ÷ capacidade da sala. Conforme a ocupação, a aula é classificada em quente (≥ 85%), morna (70–85%), fria (40–70%) ou gelada (< 40%). Só aulas frias e geladas são indicadas para promoção. |

### 5.2 Indicadores por aula

| Indicador | Cálculo | Para que serve |
|---|---|---|
| Aulas no período | datas com chamada registrada | base das médias; aula sem chamada aparece como "sem dados" |
| Média de presentes | presenças ÷ aulas no período | ranking das aulas mais frequentadas |
| Ocupação real | média de presentes ÷ capacidade da sala | temperatura da aula (RN17) |
| Lugares vazios | capacidade − média de presentes | vacância por aula; somada, dá os lugares vazios por semana |
| Frequência | presenças ÷ (presenças + faltas) | separa falta de vaga de falta de engajamento |
| Avulsos | presenças de alunos sem matrícula ativa na data (RN08) | demanda que pode virar matrícula |
| Tendência | média da 2ª metade do período vs. 1ª metade, em %; exige pelo menos 4 aulas | indica se a aula está esquentando ou esfriando |

Só entram aulas ativas. Uma aula é semanal, então "por aula" e "por semana" são equivalentes.

### 5.3 Regras das sugestões

| Situação | Sugestão exibida |
|---|---|
| Quente (≥ 85%) | Sem promoção; há demanda para abrir outra turma da modalidade ou rever o valor. |
| Morna (70–85%) | Manter; promoções só pontuais. |
| Fria (40–70%) | Promoção leve: aula experimental grátis, "traga um amigo" ou pacote no horário. |
| Gelada (< 40%) | Promoção forte, ou mudar o dia/horário ou juntar com outra turma. |
| Tendência ≤ −15% | Aviso de queda: agir antes que a aula esfrie mais. Aulas quentes ou mornas em queda aparecem em "Esfriando". |
| Tendência ≥ +15% em aula fria ou gelada | A aula está aquecendo; talvez baste divulgar mais. |
| Frequência < 70% | O problema é engajamento, não vaga: contatar os alunos faltosos. |
| Avulsos ≥ 20% das presenças | Oferecer pacote de adesão aos avulsos. |

Os limites das faixas ficam em `CONSULTAS_FAIXAS`, no `settings.py`. Os demais limites (15%, 70%, 20%) são constantes em `consultas/services.py`.

### 5.4 Por que esses critérios

Não foi encontrado um projeto open source no GitHub que faça essa consulta. Os sistemas de gestão de academias e estúdios encontrados têm só partes da ideia, como gráfico de alunos por estilo ou mapa de calor de presença. Os critérios seguem o que os sistemas comerciais do setor usam:

- **Medir presença, não inscrição:** a ocupação ("utilização") é a fração de lugares realmente usados. A [fitdegree](https://fitdegree.com/post/how-to-build-a-class-schedule-that-maximizes-revenue-per-square-foot) relata 33% de não comparecimento quando se conta a inscrição.
- **Faixa saudável de 70–85%:** a [Zenoti](https://www.zenoti.com/en-uk/thecheckin/5-profit-boosting-fitness-business-metrics-youre-not-tracking-but-should-be) recomenda 75–85%, e a [ClassPass](https://classpass.com/partners/blog/tips-for-crafting-your-class-schedule) sugere 70% como mínimo para manter a aula na grade.
- **Aula cheia pede nova turma, não desconto:** também na Zenoti.
- **Promoções para horários vazios:** a [Zipper](https://www.joinzipper.com/blog/how-to-actually-fill-your-classes-without-burning-out) sugere preço menor ou cartela fidelidade, e a [Mindbody](https://www.mindbodyonline.com/en-au/business/education/blog/how-update-your-fitness-studio-pricing) sugere preço dinâmico. A [Vibefam](https://vibefam.com/how-fitness-studios-can-monetize-off-peak-hours-without-discounting/) desaconselha desconto generalizado, por isso a sugestão para aulas frias é uma promoção leve e direcionada.
- **Mapa de calor por dia e horário:** [Club Automation](https://www.clubautomation.com/resources/why-member-attendance-heatmaps-and-trend-analysis-tools-matter-for-enterprise-fitness-clubs).

Esses números são referências de mercado para academias, não de escolas de dança. Vale ajustá-los com a escola, especialmente a capacidade: em dança a dois, a lotação confortável pode ser menor que os 40 lugares da sala (RN09).

### 5.5 Resultado com os dados de demonstração (8 semanas até 10/11/2026)

- Ocupação média de 45% (fria), 1.359 presenças em 76 aulas e cerca de 221 lugares vazios por semana.
- Nenhuma aula quente ou morna: 7 frias e 3 geladas.
- Mais frequentada: Zouk iniciante (segunda 20h), com média de 24,8 presentes, ou 62%.
- Geladas: Zouk avançado (sábado 18h30, 24%), Forró iniciante (segunda 19h, 29%) e Zouk intermediário (quarta 20h, 32%).

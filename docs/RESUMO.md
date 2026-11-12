# Portal da Dança — Resumo da revisão e da implementação

## Equipe

FATEC Rubens Lara — Análise e Desenvolvimento de Sistemas — Projeto Integrador em Análise e Desenvolvimento de Sistemas I, 2º semestre de 2026. Professora orientadora: Rosemeire Cardozo Vidal.

- Cauêt da Silva
- Davi Andrade Zenha
- Douglas Macedo
- Fernando Luiz Branco Freire
- Gabriel Lane Valiengo Regis
- Gabriel Pinto Gonçalves
- João Gabriel Couceiro Rampon
- Maria Eduarda Inocencio Costa
- Nícolas Vendramini Dutra
- Rayck Barbosa Fernandes
- Rodrigo Conde Attanasio

## Sobre o projeto

Este sistema é um projeto da disciplina **Projeto Integrador em Análise e Desenvolvimento de Sistemas I**, do curso de Análise e Desenvolvimento de Sistemas da **FATEC Rubens Lara**, desenvolvido no 2º semestre de 2026 sob a orientação da **Professora Rosemeire Cardozo Vidal**.

É também um **projeto social**: um software produzido na FATEC e devolvido à sociedade. Pequenas escolas de dança, estúdios e outros negócios que organizam aulas por turmas costumam depender de planilhas e não têm acesso a sistemas de gestão pagos. Por isso o código é aberto e de **uso gratuito**, sob a licença MIT.

O sistema foi feito para atender a Portal da Dança, mas foi organizado para poder ser adaptado por outras escolas e empresas, do estado, do país ou de qualquer lugar. Os módulos são separados, as regras de negócio estão documentadas e testadas, e salas, modalidades, horário de funcionamento e os limites da consulta de oportunidades são configuráveis.

### Licença

Distribuído sob a **licença MIT** (veja o arquivo `LICENSE`). Qualquer pessoa ou empresa pode usar, copiar, modificar e distribuir o sistema gratuitamente, inclusive para fins comerciais, desde que mantenha o aviso de direitos autorais e a licença. O software é oferecido "como está", sem garantia.

Quem adotar o sistema em outra escola deve revisar as regras configuráveis e cuidar das obrigações da LGPD no próprio uso, já que o sistema guarda dados pessoais de alunos.

## Versão 1.0 (10/11/2026)

- **Relatório final:** `docs/relatorio/Relatorio_Portal_da_Danca_v1.0.docx` e `.pdf`. Traz RF01–RF25, RNF01–RNF08 e RN01–RN17, a rastreabilidade, o protótipo e a verificação: 150 testes aprovados e Semgrep sem problemas (188 regras).
- **Fluxogramas:** `docs/fluxogramas/Portal_da_Danca_Fluxogramas_v1.0.drawio` (editável) e `.pdf`, numerados de 00 a 17. Para regerar: `python3 docs/fluxogramas/gerar_fluxogramas.py`.
- **Salário por matrícula:** alunos inscritos nas aulas do professor no mês × valor por aluno. Cada par aluno–aula conta uma vez; alunos avulsos não contam; faltas não reduzem o valor (RN07, RN16).
- **Matrícula com histórico:** inscrever um aluno numa aula abre uma matrícula com data de início; desinscrever encerra com data de fim. O histórico aparece na tela de cada aula.
- **Consulta de frequência e oportunidades** (menu 🌡️ Consultas; RF25, RN17): para o proprietário, mostra as aulas mais frequentadas e onde vale fazer promoção. Detalhes na seção 5 da Análise.
- **Auditoria:** quem acessou, de qual IP e o que alterou fica em `logs/`; resumo com `python manage.py relatorio_acessos`.
- **Implantação:** o sistema roda como serviço (gunicorn e systemd) na porta 3010; veja "Como rodar".

## Observações da professora

Ela deixou dois comentários, e o relatório revisado responde aos dois:

- **Após o RF16** ("adicionar ou remover aulas e horários, cadastro de professores, quantidade de alunos por aula"): os RF17–RF21 cobrem isso.
- **Após o RN07** ("regras para os alunos: matrícula, pagamento em dia, tolerância, taxas, exame médico"): o RN08 agora diz que a escola não adota nenhuma dessas regras. Por isso o sistema nunca bloqueia um aluno. A situação da mensalidade é apenas informativa, e alunos não vinculados a uma aula ainda podem receber presença.

Os pontos que ela destacou também foram corrigidos:

- O RF05 (controle de entrada e saída, estilo catraca) virou "consulta da agenda de aulas".
- O RF08 agora separa a forma de pagamento (Pix, dinheiro, cartão) da origem do dinheiro (mensalidade, aluguel de sala, bebidas, camisetas).
- O RF13 agora explica como o salário dos professores é calculado.

Também entraram no relatório a correção de lançamentos financeiros (RF23, fluxo 15) e o acesso ao sistema (RF22, fluxo 00). Ainda falta confirmar com a escola:

- **O valor pago por aluno inscrito.** O relatório não informa, então ficou configurável no cadastro de cada professor.
- **Os limites da consulta de oportunidades (RN17)** e a lotação confortável de cada sala em dança a dois, que pode ser menor que 40.

## Problemas nos fluxogramas da versão preliminar

Todos foram corrigidos nos fluxogramas atuais.

- **Fluxo 01 (alunos):** a seta de "Solicitar correção" vai para "Cadastrar aluno", então dados inválidos seriam salvos. Ela deve voltar para a etapa de entrada.
- **Fluxo 04 (agendamento):**
  - Não verifica duas aulas na mesma sala no mesmo horário, nem professor com duas aulas ao mesmo tempo.
  - O ramo "mais de 40 alunos" simplesmente termina, sem voltar.
  - Nada cobre atualizar ou remover uma aula agendada.
- **Fluxo 06 (presença):** não há caminho para um aluno não vinculado à aula, o que o RN08 permite.
- **Fluxo 10 (mensalidades):** nunca pede a forma de pagamento, exigida pelo RN02/RN12, nem a data de validade.
- **Formas:** os fluxos 03 e 08 desenham decisões como paralelogramos em vez de losangos. O fluxo 09 esconde o cálculo do salário dentro da etapa de categoria.
- **Numeração:** os fluxos 05, 07 e 11 não existem nas tabelas de rastreabilidade.

As tabelas completas estão em `docs/ANALISE.md`.

## O que foi construído

- **alunos/** e **professores/:** páginas de cadastro, busca, atualização e detalhe para alunos (RF01–02) e professores (RF17).
- **aulas/:**
  - Modalidades e salas (RF18). As 2 salas de 40 lugares e as 6 modalidades são criadas automaticamente.
  - Agenda semanal com filtros (RF05, RF19).
  - Rejeita aulas fora do horário 18h–22h, choque de sala e choque de professor.
  - Alunos vinculados a uma aula, limitados pela capacidade da sala (RF20–21).
  - Chamada por data, com alunos avulsos, mais uma consulta de presenças e faltas (RF03–04).
- **financeiro/:**
  - Lançamentos de entrada e saída, com as regras RN01–04 aplicadas no modelo.
  - Mensalidades, despesas, lista de movimentações com filtros, saldo e balanço mensal (RF06–RF16).
  - Salário do professor = alunos inscritos (matrículas ativas no mês) nas aulas dele × valor por aluno, registrado como saída (RF13, RN07, RN16).
- **consultas/:** consulta de frequência e oportunidades para o proprietário (RF25, RN17).
  - Ocupação real = média de alunos *presentes* por aula ÷ capacidade da sala. Cada aula ganha uma temperatura: 🔥 quente (≥ 85%), 🌤️ morna (70–85%), ❄️ fria (40–70%) ou 🧊 gelada (< 40%).
  - Mapa de calor da agenda, ranking das aulas mais frequentadas, presenças por semana, ocupação por modalidade e cartões com sugestão de promoção para as aulas frias e geladas.
  - Não grava nada: tudo vem das chamadas e matrículas. Limites ajustáveis em `CONSULTAS_FAIXAS`, no `settings.py`.
- **Segurança:** todas as páginas exigem login, os formulários são protegidos contra envios forjados (CSRF) e o link de "voltar" não pode levar para sites externos.
- **Decisões de projeto:**
  - Uma aula com histórico de presenças não pode ser excluída, porque isso apagaria a base dos salários já pagos. A tela orienta a marcá-la como inativa.
  - O arquivo CSS original estava cortado no meio; foi completado, incluindo o layout para celular.
- **Dados do protótipo:** `python manage.py popular_demo` cria 60 alunos, 4 professores, 10 aulas, cerca de 2 mil registros de presença e 3 meses de financeiro. Também cria o login de demonstração (usuário `responsavel`), como administrador. A senha vem de `--senha` ou da variável `DJANGO_DEMO_SENHA`; sem nenhuma das duas, uma senha aleatória é gerada e exibida uma única vez no terminal.
- **Testes:** cada teste indica o requisito (RF/RN) que verifica. Rode com `.venv/bin/python manage.py test`.

## Como rodar

### Instalação rápida (Windows, macOS e Linux)

Com o Python 3.12 ou mais novo instalado, na pasta do projeto:

| Sistema | Instalar | Abrir o sistema |
|---|---|---|
| Windows | `py portal.py instalar` | `py portal.py iniciar` |
| macOS e Linux | `python3 portal.py instalar` | `python3 portal.py iniciar` |

Depois acesse `http://127.0.0.1:8000/` com o usuário `responsavel` e a senha mostrada no fim da instalação. Outros comandos: `iniciar --rede` (acesso pela rede), `iniciar --porta 8080`, `senha` (trocar a senha), `senha --novo` (novo usuário), `testar` e `instalar --sem-demo`. A lista completa está no `README.md` e em `python3 portal.py --help`.

O `portal.py` executa os mesmos passos descritos abaixo, que continuam valendo para quem preferir fazer à mão.

### Depois de clonar o repositório

O repositório traz só o código e a documentação. Alguns arquivos ficam de fora de propósito (veja o `.gitignore`) e precisam ser recriados em cada máquina:

| Fica de fora | Por quê | Como recriar |
|---|---|---|
| `.venv/` | ambiente Python, específico de cada máquina | `python3 -m venv .venv` e `pip install -r requirements.txt` |
| `db.sqlite3` | banco com dados pessoais dos alunos (LGPD) | `migrate` e, para testes, `popular_demo` |
| `.secret_key` | chave secreta do Django | gerada sozinha no primeiro uso |
| `.env` | configuração do servidor | criar à mão, só no servidor (veja "Em produção") |
| `logs/` | auditoria, com usuários e IPs | criada sozinha no primeiro uso |
| `staticfiles/` | cópia dos arquivos de estilo, gerada | `collectstatic` |

É preciso Python 3.12 ou mais novo (o servidor usa o 3.14). Os comandos abaixo são para Linux e macOS; no Windows, use o `portal.py` (veja "Instalação rápida").

O código está no branch `testes`, por isso o `-b testes`:

```bash
git clone -b testes https://github.com/rasollo/escoladedanca.git project
cd project
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
DJANGO_DEMO_SENHA='escolha-uma-senha' .venv/bin/python manage.py popular_demo   # dados de demonstração (opcional)
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py test          # opcional: roda os 150 testes
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Sem a variável `DJANGO_DEMO_SENHA`, o `popular_demo` gera uma senha aleatória e a mostra uma única vez.

Se outras máquinas forem acessar e houver firewall, libere a porta antes de iniciar: `sudo ufw allow 8000/tcp`. Não use a porta 3010 no servidor: ela já é ocupada pelo serviço de produção.

Acesse `http://<ip-da-máquina>:8000/` (ou `http://127.0.0.1:8000/` na própria máquina) e entre com o usuário `responsavel` e a senha definida acima. Para trocar depois: `.venv/bin/python manage.py changepassword responsavel`. Sem o `popular_demo`, o banco começa vazio; crie um usuário com `.venv/bin/python manage.py createsuperuser`.

O sistema em produção fica em `http://192.168.88.10:3010/` (rede local da escola) ou `http://10.8.0.1:3010/` (pela VPN).

Nunca envie para o repositório o `db.sqlite3`, o `.env`, o `.secret_key` nem a pasta `logs/`. Antes de cada commit, confira com `git status`.

### Em produção (serviço)

O `runserver` acima é só para desenvolvimento. No servidor, o sistema roda com gunicorn pelo serviço `escoladedanca` do systemd, que lê a configuração de `project/.env` (`DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `AUDITORIA_DIAS_RETENCAO`).

```bash
sudo systemctl status escoladedanca     # situação do serviço
sudo systemctl restart escoladedanca    # depois de alterar código ou o .env
journalctl -u escoladedanca -f          # acompanhar o log
sudo systemctl enable escoladedanca     # iniciar junto com o servidor
```

O gunicorn não serve arquivos estáticos; quem serve o CSS é o WhiteNoise, a partir de `project/staticfiles/`. O projeto no servidor fica em `/home/escoladanca/project` e pertence ao usuário `escoladanca`, então os comandos do `manage.py` rodam como ele. Depois de mudar qualquer CSS, rode:

```bash
cd /home/escoladanca/project
sudo -u escoladanca .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart escoladedanca
```

Nenhuma senha ou chave fica no código: a `SECRET_KEY` vem de `DJANGO_SECRET_KEY` ou é gerada no primeiro uso em `.secret_key` (ignorado pelo git).

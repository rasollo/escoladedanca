####################################################
# FATEC/BS - Prof. Rubens Lara
# Escola de Dança - Projeto Integrador
# Projeto – Sistema de Gestão para Escola de Dança

## Sobre o projeto

Este sistema é um projeto da disciplina **Projeto Integrador em Análise e Desenvolvimento de Sistemas I**, do curso de Análise e Desenvolvimento de Sistemas da **FATEC Rubens Lara**, desenvolvido no 2º semestre de 2026 sob a orientação da **Professora Rosemeire Cardozo Vidal**.

É também um **projeto social**: um software produzido na FATEC e devolvido à sociedade. Pequenas escolas de dança, estúdios e outros negócios que organizam aulas por turmas costumam depender de planilhas e não têm acesso a sistemas de gestão pagos. Por isso o código é aberto e de **uso gratuito**, sob a licença MIT.

O sistema foi feito para atender a Portal da Dança, mas foi organizado para poder ser adaptado por outras escolas e empresas, do estado, do país ou de qualquer lugar. Os módulos são separados, as regras de negócio estão documentadas e testadas, e salas, modalidades, horário de funcionamento e os limites da consulta de oportunidades são configuráveis.

## Como instalar e testar

Qualquer pessoa pode instalar e usar o sistema no próprio computador. Você vai precisar de:

* **Python 3.12 ou mais novo**;
* **internet** durante a instalação, para baixar as dependências;
* uns **10 minutos**.

Escolha o seu sistema operacional e siga os passos em ordem.

---

### 🪟 Windows

**1. Instale o Python**

Baixe em [python.org/downloads](https://www.python.org/downloads/) e execute o instalador.

> ⚠️ Na primeira tela do instalador, **marque a opção "Add Python to PATH"** antes de clicar em *Install Now*.

Se preferir, instale pelo terminal: `winget install Python.Python.3.12`

**2. Baixe o projeto**

* **Sem git:** no GitHub, clique em **Code → Download ZIP** e descompacte, por exemplo em `Documentos\escoladedanca`.
* **Com git:** `git clone https://github.com/rasollo/escoladedanca.git`

**3. Abra o terminal na pasta do projeto**

Abra a pasta no Explorador de Arquivos, clique na barra de endereço, digite `powershell` e pressione Enter.

**4. Instale**

```powershell
py portal.py instalar
```

> Se aparecer *"py não é reconhecido"*, use `python portal.py instalar`.

**5. Abra o sistema**

```powershell
py portal.py iniciar
```

Acesse **http://127.0.0.1:8000/** no navegador. Para parar, pressione `Ctrl + C` no terminal.

---

### 🐧 Linux (Ubuntu, Debian, Mint, Fedora…)

**1. Instale o Python e o git**

```bash
# Ubuntu, Debian e Mint
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git

# Fedora
sudo dnf install -y python3 git
```

Confira a versão com `python3 --version`; ela precisa ser 3.12 ou mais nova.

**2. Baixe o projeto**

```bash
git clone https://github.com/rasollo/escoladedanca.git
cd escoladedanca
```

**3. Instale**

```bash
python3 portal.py instalar
```

**4. Abra o sistema**

```bash
python3 portal.py iniciar
```

Acesse **http://127.0.0.1:8000/** no navegador. Para parar, pressione `Ctrl + C` no terminal.

---

### 🍎 macOS

**1. Instale o Python**

Baixe o instalador para macOS em [python.org/downloads](https://www.python.org/downloads/) e execute. Quem usa Homebrew pode instalar com `brew install python`.

**2. Baixe o projeto**

Abra o **Terminal** (Aplicativos → Utilitários → Terminal):

```bash
git clone https://github.com/rasollo/escoladedanca.git
cd escoladedanca
```

> Na primeira vez que você usar o `git`, o macOS pode oferecer as "ferramentas de linha de comando": aceite. Se não quiser usar o git, baixe o ZIP pelo GitHub (**Code → Download ZIP**), descompacte e entre na pasta com `cd`.

**3. Instale**

```bash
python3 portal.py instalar
```

**4. Abra o sistema**

```bash
python3 portal.py iniciar
```

Acesse **http://127.0.0.1:8000/** no navegador. Para parar, pressione `Ctrl + C` no terminal.

---

### O que o instalador faz

1. Cria o ambiente Python do projeto (pasta `.venv`). Nada é instalado no resto do computador.
2. Instala as dependências (`requirements.txt`).
3. Cria o banco de dados e carrega os **dados de demonstração**.
4. Prepara os arquivos de estilo.

No fim, ele mostra os acessos criados. **Anote a senha**, porque ela só aparece uma vez.

### Acessos de demonstração

| Usuário | Papel | O que dá para testar |
|---|---|---|
| `responsavel` | Administrativo | Todo o sistema: cadastros, aulas, mensalidades, relatórios e acessos |
| `camila.rocha` | Professor **e** Aluno | Escolha de ambiente, portal do professor, chamadas e comunicados |
| aluno indicado no fim da instalação | Aluno | Portal do aluno: aulas, mensalidades e solicitações |

Para escolher você mesmo a senha da demonstração: `instalar --senha MINHA_SENHA`.

### Comandos úteis

No Windows, use `py` no lugar de `python3`.

| Comando | O que faz |
|---|---|
| `python3 portal.py instalar --senha MINHA_SENHA` | instala com uma senha escolhida por você |
| `python3 portal.py instalar --sem-demo` | instala com o banco vazio, sem demonstração |
| `python3 portal.py iniciar --porta 8080` | usa outra porta |
| `python3 portal.py iniciar --rede` | permite o acesso de outros computadores da rede, pelo IP desta máquina |
| `python3 portal.py senha` | troca a senha do usuário `responsavel` |
| `python3 portal.py senha --novo` | cria um novo usuário administrador |
| `python3 portal.py testar` | roda os testes automatizados |

### Atualizar para uma versão nova

Baixe a versão nova (`git pull` ou um novo ZIP) e rode **`instalar` de novo**. O instalador atualiza o que mudou e não apaga nem duplica dados.

Para um **servidor que já está rodando com gunicorn**, o roteiro está em `docs/RESUMO.md`, na seção "Atualizar um servidor que já está rodando": backup, `git pull`, migrações, arquivos de estilo, restart do serviço, conferência e como voltar atrás.

### Problemas comuns

| Sintoma | Solução |
|---|---|
| **"py não é reconhecido"** (Windows) | O Python não está no PATH. Reinstale marcando *Add Python to PATH*, ou use `python` no lugar de `py`. |
| **"python3: command not found"** (Linux/macOS) | Instale o Python (passo 1 do seu sistema). |
| **Erro ao criar o ambiente** (Ubuntu/Debian) | `sudo apt install python3-venv` e rode o instalador de novo. |
| **"Port is already in use"** | Outra aplicação usa a porta 8000: `iniciar --porta 8080`. |
| **Erro de rede ao instalar as dependências** | Confira a internet ou o proxy da rede e rode o instalador de novo. |

> Este modo é para **testar e desenvolver**. Para usar o sistema de verdade numa escola, com HTTPS e o modo de depuração desligado, veja "Em produção" em `docs/RESUMO.md`.

## Origem do projeto

Iniciamos o projeto a partir da sugestão de um colega da turma de **ADS – Primeiro Ciclo**, com a ideia de construir um sistema para a gestão de processos internos de uma escola de dança.

A princípio, o sistema terá como prioridade o **controle de aulas e professores**, além de algumas informações importantes sobre alunos e colaboradores.

## Funcionalidades iniciais

Entre as informações que pretendemos controlar estão:

* Nome completo dos colaboradores e alunos
* Dados básicos dos alunos
* Datas importantes, como aniversário
* Tempo de participação nas aulas
* Cadastro e controle de aulas
* Cadastro e controle de professores
* Relatório básico de faturamento, cujo requisito ainda será levantado

A ideia é começar com um sistema **bem simples**, atendendo às necessidades básicas da escola, mas deixando espaço para futuras melhorias e novas funcionalidades.

## Tecnologia

Para o desenvolvimento do projeto, foi sugerida a utilização de **Python**, utilizando o framework **Django**.

A sugestão do Django também tem como objetivo proporcionar uma oportunidade para quem ainda não conhece o framework aprender uma nova tecnologia durante o desenvolvimento do projeto.

Como já tenho experiência em desenvolvimento, posso ajudar o grupo principalmente na parte de desenvolvimento e na organização da implementação.

## Segurança

Um dos motivos para a escolha do Django é a facilidade para trabalhar com **cadastro de usuários e controle de acesso**.

A ideia é utilizarmos **RBAC (Role-Based Access Control)**, permitindo definir diferentes permissões de acordo com o tipo de usuário.

Por exemplo, podemos ter diferentes níveis de acesso para:

* Administradores
* Professores
* Colaboradores
* Outros usuários do sistema

Dessa forma, podemos aproveitar o projeto para começar a implementar algumas práticas de **AppSec (Application Security)** desde o início.

Além das funcionalidades, podemos trabalhar conceitos como:

* Autenticação
* Autorização
* Controle de acesso
* Proteção das informações
* Boas práticas de desenvolvimento seguro

## Tecnologias

A escolha do Django não é obrigatória. **Qualquer linguagem ou tecnologia será bem-vinda**, desde que atenda aos requisitos definidos pelo grupo.

A sugestão do Django foi feita principalmente pela:

* Leveza
* Facilidade de implementação
* Facilidade de manutenção
* Comunidade
* Documentação
* Utilização de código aberto (**open source**)

## Próximos passos

Neste primeiro momento, precisamos definir melhor os **requisitos básicos do sistema** e dividir as tarefas entre os integrantes.

Conforme o projeto avançar, podemos levantar novos requisitos e acrescentar outras funcionalidades.

A ideia é que todos possam participar do desenvolvimento e também aprender durante o processo.

No final, esperamos ter um sistema **simples, funcional e seguro**, que possa ajudar no controle dos processos internos da escola de dança e, ao mesmo tempo, servir como uma oportunidade para colocarmos em prática os conhecimentos adquiridos durante o curso.

## Versão 2.0 (22/11/2026)

* **Relatório final atualizado:** `docs/relatorio/Relatorio_Portal_da_Danca_v2.0.pdf` (e `.docx`), com 38 requisitos funcionais, 20 regras de negócio, rastreabilidade e o print de cada tela. Também pode ser baixado pelo menu **Documentação** do sistema.
* **Novidades:**
  * visual baseado no protótipo v3, com modo escuro;
  * perfis Administrativo, Professor e Aluno, com mais de um papel na mesma conta e "Trocar ambiente";
  * mensalidades como cobranças, com recebimento parcial e estorno;
  * comunicados e solicitações;
  * matrícula suspensa ou cancelada com motivo;
  * chamada concluída, com correção justificada e cancelamento de aula;
  * aulas em vários dias e com período de vigência;
  * relatórios em CSV e backup em JSON;
  * troca de senha no primeiro acesso;
  * lista de alunos para o professor;
  * aniversariantes do mês.

## Versão 1.0 (10/11/2026)

O sistema está implementado e documentado:

* **Relatório final da v1.0:** substituído pela versão 2.0 (a v1.0 continua no histórico do git).
* **Fluxogramas:** `docs/fluxogramas/Portal_da_Danca_Fluxogramas_v1.0.pdf` (e `.drawio`, editável).
* **Resumo e análise:** `docs/RESUMO.md` e `docs/ANALISE.md`, também disponíveis no menu Documentação do sistema.
* **Como instalar:** veja "Como instalar e testar", acima.

## Perfis de acesso (RBAC)

Cada usuário tem um papel, guardado como grupo do Django e criado automaticamente pelo instalador:

| Papel | O que pode fazer |
|---|---|
| **Administrativo** | Todo o sistema: alunos, professores, aulas, chamadas, financeiro, consultas e criação/bloqueio de acessos (menu Administração → **+ Novo acesso**). O usuário `responsavel` é Administrativo. |
| **Professor** | Ver a própria área (aulas, inscritos e salário estimado), agendar e editar as próprias aulas (respeitando a lotação da sala, o horário 18h–22h e os conflitos), vincular alunos às suas aulas até a lotação, fazer a chamada e consultar as presenças das suas turmas. |
| **Aluno** | Ver as aulas em que está matriculado, a agenda, as próprias presenças/faltas e mensalidades. |

Com os dados de demonstração, o instalador cria também um acesso de **professor** (`camila.rocha`) e um de **aluno** (um aluno que faz aniversário no mês), com a mesma senha do `responsavel`. Os logins aparecem no fim da instalação. Com `--sem-demo`, nenhum desses acessos é criado.

O acesso é **negado por padrão**: uma página só abre para Professor ou Aluno quando liberada explicitamente no código (`escoladedanca/rbac.py`). Para dar acesso a um professor ou aluno, cadastre-o normalmente e, na página dele, use **criar acesso**. Os logs de auditoria (IPs e acessos) continuam visíveis só para a equipe técnica (`is_staff`).

Todas as datas são exibidas e digitadas no formato **dd/mm/aaaa**.

### Mensalidades (cobranças)

Cada aula tem um valor de mensalidade, que é copiado para a matrícula no momento da inscrição; a matrícula pode ter desconto percentual ou fixo. Em **Mensalidades → Gerar cobranças**, o sistema cria uma cobrança por matrícula ativa no mês, com vencimento no dia 5 (`ESCOLA_DIA_VENCIMENTO`). Gerar de novo não duplica. A cobrança não muda o caixa: o saldo só muda quando um recebimento é confirmado, e o recebimento pode ser parcial, mas nunca acima do saldo devedor. Para corrigir um recebimento, use o **estorno**, que exige motivo e preserva o histórico. A situação (pendente, parcial, atrasada ou paga) é só informativa: nenhum aluno é bloqueado.

### Comunicados e solicitações

- **Comunicados:** a administração e os professores publicam avisos por aula. Cada aluno vê os avisos das aulas em que está matriculado.
- **Solicitações:** o aluno pede correção cadastral, revisão de frequência, mudança de matrícula ou tira dúvidas sobre a mensalidade, e a administração responde. Nada é alterado automaticamente.

### Visual

O visual segue o protótipo v3: fontes DM Sans e Manrope, menu lateral com o cartão "Ambiente atual" e modo escuro (botão no topo; a escolha fica salva no navegador). Qualquer usuário altera a própria senha pelo ícone de cadeado no rodapé do menu.

### Aniversariantes do mês

Os três papéis veem o menu **Aniversariantes** e um quadro no painel inicial com os alunos e professores ativos que fazem aniversário no mês. Administrativo e Professor veem também a idade que a pessoa completa; o Aluno vê só o dia e o mês. O ano de nascimento não aparece para ninguém nessa tela. A data de nascimento continua **opcional** no cadastro de alunos e professores.

Os dados de demonstração do instalador já trazem datas de nascimento, com aniversariantes sempre no mês atual. Em uma instalação de demonstração já existente, rode `python3 portal.py instalar` de novo para completar as datas: só os registros de demonstração são alterados.

## Time

FATEC Rubens Lara — Análise e Desenvolvimento de Sistemas — Projeto Integrador em Análise e Desenvolvimento de Sistemas I, 2º semestre de 2026. Professora orientadora: Rosemeire Cardozo Vidal.

* Cauêt da Silva
* Davi Andrade Zenha
* Douglas Macedo
* Fernando Luiz Branco Freire
* Gabriel Lane Valiengo Regis
* Gabriel Pinto Gonçalves
* João Gabriel Couceiro Rampon
* Maria Eduarda Inocencio Costa
* Nícolas Vendramini Dutra
* Rayck Barbosa Fernandes
* Rodrigo Conde Attanasio

## Licença

Distribuído sob a **licença MIT** (veja o arquivo `LICENSE`). Qualquer pessoa ou empresa pode usar, copiar, modificar e distribuir o sistema gratuitamente, inclusive para fins comerciais, desde que mantenha o aviso de direitos autorais e a licença. O software é oferecido "como está", sem garantia.

Quem adotar o sistema em outra escola deve revisar as regras configuráveis e cuidar das obrigações da LGPD no próprio uso, já que o sistema guarda dados pessoais de alunos.

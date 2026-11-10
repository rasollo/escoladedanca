####################################################
# FATEC/BS - Prof. Rubens Lara
# Escola de Dança - Projeto Integrador
# Projeto – Sistema de Gestão para Escola de Dança

## Sobre o projeto

Este sistema é um projeto da disciplina **Projeto Integrador em Análise e Desenvolvimento de Sistemas I**, do curso de Análise e Desenvolvimento de Sistemas da **FATEC Rubens Lara**, desenvolvido no 2º semestre de 2026 sob a orientação da **Professora Rosemeire Cardozo Vidal**.

É também um **projeto social**: um software produzido na FATEC e devolvido à sociedade. Pequenas escolas de dança, estúdios e outros negócios que organizam aulas por turmas costumam depender de planilhas e não têm acesso a sistemas de gestão pagos. Por isso o código é aberto e de **uso gratuito**, sob a licença MIT.

O sistema foi feito para atender a Portal da Dança, mas foi organizado para poder ser adaptado por outras escolas e empresas, do estado, do país ou de qualquer lugar. Os módulos são separados, as regras de negócio estão documentadas e testadas, e salas, modalidades, horário de funcionamento e os limites da consulta de oportunidades são configuráveis.

## Como instalar e testar

Qualquer pessoa pode instalar e usar o sistema. É preciso ter o **Python 3.12 ou mais novo** ([python.org/downloads](https://www.python.org/downloads/)); no Windows, marque a opção "Add Python to PATH" ao instalar.

**1. Baixe o projeto**, de um destes jeitos:

* com o git: `git clone https://github.com/rasollo/escoladedanca.git`
* sem o git: no GitHub, clique em **Code → Download ZIP** e descompacte

**2. Abra o terminal na pasta do projeto** (no Windows: PowerShell ou Prompt de Comando) e instale:

| Sistema | Comando |
|---|---|
| Windows | `py portal.py instalar` |
| macOS e Linux | `python3 portal.py instalar` |

O instalador cria o ambiente Python (`.venv`), instala as dependências, cria o banco de dados, carrega dados de demonstração e prepara os arquivos de estilo. No fim, ele mostra a **senha** do usuário `responsavel`: anote, porque ela só aparece uma vez.

**3. Abra o sistema:**

| Sistema | Comando |
|---|---|
| Windows | `py portal.py iniciar` |
| macOS e Linux | `python3 portal.py iniciar` |

Acesse **http://127.0.0.1:8000/** no navegador e entre com o usuário `responsavel`. Para parar, pressione Ctrl+C no terminal.

**Outros comandos** (no Windows, troque `python3` por `py`):

| Comando | O que faz |
|---|---|
| `python3 portal.py instalar --senha MINHA_SENHA` | instala usando uma senha escolhida por você |
| `python3 portal.py instalar --sem-demo` | instala com o banco vazio, sem dados de demonstração |
| `python3 portal.py iniciar --porta 8080` | usa outra porta |
| `python3 portal.py iniciar --rede` | deixa outras máquinas da rede acessarem, pelo IP deste computador |
| `python3 portal.py senha` | troca a senha do usuário `responsavel` |
| `python3 portal.py senha --novo` | cria um novo usuário administrador |
| `python3 portal.py testar` | roda os testes automatizados |

O instalador pode ser executado de novo a qualquer momento, por exemplo depois de baixar uma versão nova: ele atualiza o que mudou e não duplica os dados.

Problemas comuns:

* **"python3 não encontrado"** (macOS/Linux) ou **"py não é reconhecido"** (Windows): o Python não está instalado ou não está no PATH. No Windows, tente também `python portal.py instalar`.
* **Ubuntu/Debian, erro ao criar o ambiente:** instale o módulo venv (`sudo apt install python3-venv`) e rode o instalador de novo.
* **"Port is already in use":** outra aplicação usa a porta 8000; use `iniciar --porta 8080`.

Este modo é para testar e desenvolver. Para colocar o sistema em uso numa escola, com o modo de depuração desligado, veja "Em produção" em `docs/RESUMO.md`.

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

## Versão 1.0 (10/11/2026)

O sistema está implementado e documentado:

* **Relatório final:** `docs/relatorio/Relatorio_Portal_da_Danca_v1.0.pdf` (e `.docx`), com requisitos, rastreabilidade, protótipo e verificação.
* **Fluxogramas:** `docs/fluxogramas/Portal_da_Danca_Fluxogramas_v1.0.pdf` (e `.drawio`, editável).
* **Resumo e análise:** `docs/RESUMO.md` e `docs/ANALISE.md`, também disponíveis no menu Documentação do sistema.
* **Como instalar:** veja "Como instalar e testar", acima.

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

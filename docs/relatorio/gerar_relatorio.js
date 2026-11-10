/*
 * Gera docs/relatorio/Relatorio_Portal_da_Danca_v1.0.docx (versão 1.0)
 * Requer: npm install docx@9.5.1   (fora do projeto ou com NODE_PATH apontando para ele)
 * A rastreabilidade é montada a partir de ../fluxogramas/fluxos.json, gerado por
 * gerar_fluxogramas.py, para que relatório e fluxogramas nunca divirjam.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, ShadingType, BorderStyle, HeadingLevel, LevelFormat, PageBreak, Footer,
  PageNumber, TableLayoutType,
} = require("docx");

const AQUI = __dirname;
const FLUXOS = JSON.parse(fs.readFileSync(path.join(AQUI, "../fluxogramas/fluxos.json"), "utf8"));
const VER = JSON.parse(fs.readFileSync(path.join(AQUI, "verificacao.json"), "utf8"));

const AZUL = "1F4E79", CINZA = "F2F5FA", BORDA = "C9D3E0";
const LARGURA = 9638; // A4 com margens de 2 cm

// ---------------------------------------------------------------- helpers
const t = (text, o = {}) => new TextRun({ text, font: "Arial", size: 22, ...o });
const p = (conteudo, o = {}) => new Paragraph({
  children: (Array.isArray(conteudo) ? conteudo : [conteudo]).map(c => typeof c === "string" ? t(c) : c),
  spacing: { after: 120, line: 300 }, ...o,
});
const corpo = (texto) => p(texto, { alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 567 } });
const h1 = (texto) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(texto)] });
const h2 = (texto) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(texto)] });
const bullet = (conteudo) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: (Array.isArray(conteudo) ? conteudo : [conteudo]).map(c => typeof c === "string" ? t(c) : c),
  spacing: { after: 80, line: 290 },
});
const quebra = () => new Paragraph({ children: [new PageBreak()] });

const borda = { style: BorderStyle.SINGLE, size: 4, color: BORDA };
const bordas = { top: borda, bottom: borda, left: borda, right: borda };

function tabela(cabecalho, linhas, larguras, opts = {}) {
  const total = larguras.reduce((a, b) => a + b, 0);
  const cel = (texto, w, i, cab) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: bordas,
    shading: cab ? { type: ShadingType.CLEAR, fill: AZUL, color: "auto" }
      : (i % 2 ? { type: ShadingType.CLEAR, fill: CINZA, color: "auto" } : undefined),
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: opts.centro && opts.centro.includes(larguras.indexOf(w)) ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: (Array.isArray(texto) ? texto : [texto]).map(x => typeof x === "string"
        ? t(x, { size: 19, bold: cab, color: cab ? "FFFFFF" : undefined }) : x),
    })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: larguras,
    layout: TableLayoutType.FIXED,
    rows: [
      new TableRow({ tableHeader: true, children: cabecalho.map((c, j) => cel(c, larguras[j], 0, true)) }),
      ...linhas.map((l, i) => new TableRow({ cantSplit: true, children: l.map((c, j) => cel(c, larguras[j], i, false)) })),
    ],
  });
}
const espaco = () => new Paragraph({ children: [], spacing: { after: 120 } });

function requisito(r) {
  return [
    new Paragraph({ keepNext: true, spacing: { before: 160, after: 40 }, children: [t(`${r.id} — ${r.titulo}`, { bold: true })] }),
    p(r.texto, { alignment: AlignmentType.JUSTIFIED }),
  ];
}

// ---------------------------------------------------------------- conteúdo
const ALUNOS = ["Cauêt da Silva", "Davi Andrade Zenha", "Douglas Macedo", "Fernando Luiz Branco Freire",
  "Gabriel Lane Valiengo Regis", "Gabriel Pinto Gonçalves", "João Gabriel Couceiro Rampon",
  "Maria Eduarda Inocencio Costa", "Nícolas Vendramini Dutra", "Rayck Barbosa Fernandes", "Rodrigo Conde Attanasio"];

const RF = [
  ["RF01", "Cadastro de alunos", "O sistema deve permitir que o responsável pela escola cadastre os alunos, sendo o nome o único dado obrigatório.", "Mantido"],
  ["RF02", "Consulta e atualização de alunos", "O sistema deve permitir que o responsável consulte os alunos cadastrados, com busca por nome, e-mail ou telefone, e atualize seus dados.", "Alterado"],
  ["RF03", "Registro de presença", "O sistema deve permitir que o responsável registre a presença dos alunos em cada aula agendada, na data em que a aula acontece.", "Mantido"],
  ["RF04", "Registro e consulta de faltas", "O sistema deve permitir que o responsável registre as faltas e consulte presenças e faltas, filtrando por aluno, aula, situação e período.", "Alterado"],
  ["RF05", "Consulta da agenda de aulas", "O sistema deve permitir que o responsável consulte as aulas agendadas previamente, com modalidade, sala, dia, horário, professor e quantidade de inscritos, filtrando por dia, modalidade e sala.", "Mantido"],
  ["RF06", "Registro de entradas financeiras", "O sistema deve permitir que o responsável registre entradas financeiras.", "Mantido"],
  ["RF07", "Registro de saídas financeiras", "O sistema deve permitir que o responsável registre saídas financeiras.", "Mantido"],
  ["RF08", "Classificação das entradas", "O sistema deve permitir classificar cada entrada pela forma de pagamento aceita pela escola (Pix, dinheiro ou cartão) e pela sua origem (mensalidade, aluguel de sala, bebidas ou camisetas).", "Mantido"],
  ["RF09", "Classificação das saídas", "O sistema deve permitir que o responsável classifique as saídas financeiras entre contas em geral, manutenção, luz, água, taxas, Prefeitura e salários dos professores.", "Mantido"],
  ["RF10", "Registro de data e validade", "O sistema deve permitir que o responsável informe a data do pagamento e, quando aplicável, a validade da movimentação financeira.", "Mantido"],
  ["RF11", "Acompanhamento de mensalidades", "O sistema deve permitir que o responsável registre e consulte as mensalidades de cada aluno, com forma de pagamento e validade. A situação da mensalidade (em dia ou não) é apenas informativa.", "Alterado"],
  ["RF12", "Controle de despesas", "O sistema deve permitir que o responsável registre e consulte as despesas da escola, filtrando por categoria.", "Mantido"],
  ["RF13", "Cálculo e consulta dos salários", "O sistema deve calcular, registrar e consultar a remuneração mensal dos professores com base na quantidade de alunos inscritos (matriculados) nas aulas de cada professor no mês, multiplicada pelo valor por aluno definido no cadastro do professor, conforme informado pela escola. O cálculo deve mostrar o detalhamento por aula e o valor já pago no mês.", "Alterado"],
  ["RF14", "Consulta das movimentações", "O sistema deve permitir que o responsável consulte as movimentações financeiras registradas, filtrando por período, tipo e texto.", "Mantido"],
  ["RF15", "Consulta do saldo", "O sistema deve permitir que o responsável consulte o saldo financeiro da escola.", "Mantido"],
  ["RF16", "Balanço financeiro mensal", "O sistema deve permitir que o responsável consulte o balanço financeiro mensal, com entradas por origem e forma de pagamento e saídas por categoria.", "Mantido"],
  ["RF17", "Cadastro de professores", "O sistema deve permitir cadastrar, consultar e atualizar os dados dos professores, incluindo o valor pago por aluno inscrito.", "Alterado"],
  ["RF18", "Cadastro e manutenção de aulas", "O sistema deve permitir cadastrar, consultar, atualizar e remover as modalidades (estilos de dança) e as salas da escola.", "Mantido"],
  ["RF19", "Agendamento de aulas e turmas", "O sistema deve permitir agendar aulas com antecedência e consultar, atualizar, desativar e remover modalidade, dia, horário, sala e turma, associando um professor responsável.", "Alterado"],
  ["RF20", "Capacidade e quantidade de alunos por aula", "O sistema deve permitir consultar a quantidade de alunos inscritos em cada aula e as vagas restantes, considerando a capacidade de até 40 alunos por sala.", "Mantido"],
  ["RF21", "Matrícula de alunos nas aulas", "O sistema deve permitir inscrever alunos nas aulas que frequentam e encerrar essas inscrições. Cada inscrição (matrícula) registra a data de início e a de fim, preservando o histórico usado no cálculo do salário. A matrícula não é exigida para participar das aulas.", "Alterado"],
  ["RF22", "Acesso ao sistema", "O sistema deve exigir usuário e senha para acessar qualquer página e permitir encerrar a sessão.", "Novo"],
  ["RF23", "Correção de lançamentos financeiros", "O sistema deve permitir editar ou excluir um lançamento financeiro registrado com erro, recalculando saldo e balanço.", "Novo"],
  ["RF24", "Auditoria de acessos e alterações", "O sistema deve registrar logins, falhas de login, logouts, páginas acessadas e alterações de dados, com usuário, IP, data e hora, e permitir que a equipe consulte esses registros.", "Novo"],
  ["RF25", "Consulta de frequência e oportunidades de promoção", "O sistema deve permitir que o proprietário consulte, para um período de 4, 8, 12 ou 26 semanas, as aulas mais frequentadas, a ocupação de cada aula e da agenda (por dia, horário e modalidade), a tendência de presença e quais aulas são candidatas a promoção, com uma sugestão de ação para cada aula.", "Novo"],
].map(([id, titulo, texto, situacao]) => ({ id, titulo, texto, situacao }));

const RNF = [
  ["RNF01", "Usabilidade", "O sistema deve apresentar uma interface simples e intuitiva, permitindo que o responsável realize registros e consultas sem complexidade desnecessária.", "Mantido"],
  ["RNF02", "Desempenho", "O sistema deve responder às operações de cadastro, registro e consulta em tempo adequado, reduzindo a lentidão existente no processo realizado por meio das planilhas.", "Mantido"],
  ["RNF03", "Segurança", "O sistema deve impedir que pessoas não autorizadas acessem as informações administrativas, financeiras e os dados dos alunos: todas as páginas exigem login, os formulários são protegidos contra envios forjados e nenhuma senha ou chave fica gravada no código-fonte.", "Alterado"],
  ["RNF04", "Proteção de dados / LGPD", "O sistema deve proteger os dados pessoais dos alunos, professores e demais pessoas cadastradas, observando a LGPD: coleta apenas os dados necessários, mantém trilha de auditoria por 180 dias sem gravar senhas nem dados pessoais além de usuário e IP, e mostra a auditoria apenas à equipe.", "Alterado"],
  ["RNF05", "Integridade dos dados", "O sistema deve armazenar de forma consistente os dados de alunos, professores, aulas, matrículas, presença e movimentações financeiras, impedindo registros incorretos ou duplicados.", "Alterado"],
  ["RNF06", "Acessibilidade", "O sistema deve facilitar a utilização por diferentes pessoas, considerando legibilidade dos textos, organização visual, contraste adequado e navegação por teclado.", "Mantido"],
  ["RNF07", "Portabilidade", "O sistema deve ser usado pelo navegador e poder ser executado no ambiente definido para a escola, sem depender de uma configuração específica de hardware.", "Mantido"],
  ["RNF08", "Armazenamento", "Os dados registrados devem ser armazenados de forma persistente, permitindo que as informações sejam consultadas posteriormente.", "Mantido"],
].map(([id, titulo, texto, situacao]) => ({ id, titulo, texto, situacao }));

const RN = [
  ["RN01", "Classificação das movimentações financeiras", "Toda movimentação financeira registrada deve ser classificada como entrada ou saída.", "Mantido"],
  ["RN02", "Classificação das entradas financeiras", "As entradas devem indicar a forma de pagamento (Pix, dinheiro ou cartão) e a origem (mensalidade, aluguel de sala, bebidas ou camisetas). Quando a origem é mensalidade, o aluno deve ser informado.", "Alterado"],
  ["RN03", "Categorias de saídas financeiras", "As saídas financeiras devem ser classificadas conforme as categorias da Portal da Dança: contas em geral, manutenção, luz, água, taxas, Prefeitura e salários dos professores.", "Mantido"],
  ["RN04", "Identificação temporal da movimentação", "Toda movimentação financeira deve possuir data de pagamento e, quando aplicável, validade, que não pode ser anterior à data do pagamento.", "Mantido"],
  ["RN05", "Apuração financeira mensal", "O balanço financeiro mensal deve comparar as entradas e as saídas financeiras realizadas no período.", "Mantido"],
  ["RN06", "Registro das mensalidades", "As mensalidades devem ser consideradas entradas financeiras da Portal da Dança.", "Mantido"],
  ["RN07", "Salários dos professores", "Os pagamentos aos professores são saídas financeiras. O valor mensal de cada professor é a quantidade de alunos inscritos (matriculados) nas suas aulas no mês, multiplicada pelo valor por aluno definido para o professor, conforme informado pela escola.", "Alterado"],
  ["RN08", "Ausência de regras específicas para matrícula e participação", "A escola não adota regras sobre matrícula obrigatória, pagamento em dia como condição para participar, prazo de tolerância, taxa de matrícula, afastamento ou exame médico. O sistema não impõe essas restrições: alunos sem matrícula podem participar e ter presença registrada (alunos avulsos), e a situação da mensalidade é apenas informativa. A matrícula serve para organizar as turmas e calcular o salário dos professores.", "Alterado"],
  ["RN09", "Salas e capacidade", "A escola possui duas salas, com capacidade informada de até 40 alunos por sala. Inscritos e presentes de uma aula não podem passar da capacidade da sala.", "Mantido"],
  ["RN10", "Agendamento prévio", "As aulas devem ser agendadas previamente, com definição de modalidade, sala, dia, horário e professor.", "Mantido"],
  ["RN11", "Registro diário das movimentações", "As movimentações financeiras da escola ocorrem diariamente e devem ser registradas para apoiar o fechamento mensal.", "Mantido"],
  ["RN12", "Formas de pagamento aceitas", "A escola aceita pagamentos por Pix, dinheiro ou cartão.", "Mantido"],
  ["RN13", "Horário de funcionamento", "As aulas só podem ser agendadas dentro do horário de funcionamento da escola, das 18h às 22h, e o término deve ser posterior ao início.", "Novo"],
  ["RN14", "Conflitos de agenda", "Não pode haver duas aulas ativas na mesma sala, nem o mesmo professor em duas aulas ativas, com horários sobrepostos no mesmo dia da semana.", "Novo"],
  ["RN15", "Preservação do histórico", "Aulas com presenças ou matrículas, e modalidades ou salas usadas por aulas, não podem ser removidas; devem ser desativadas. Desativar uma aula encerra as matrículas abertas.", "Novo"],
  ["RN16", "Contagem de inscritos para o salário", "Conta cada par aluno–aula com matrícula ativa em pelo menos um dia do mês. Um aluno inscrito em duas aulas do mesmo professor conta duas vezes; um aluno que saiu e voltou à mesma aula no mês conta uma vez; uma matrícula aberta e encerrada no mesmo dia não conta. Alunos avulsos não contam e faltas não reduzem o valor.", "Novo"],
  ["RN17", "Ocupação e temperatura das aulas", "A ocupação de uma aula é a média de alunos presentes por aula no período dividida pela capacidade da sala; inscrições sem presença não contam. Conforme a ocupação, a aula é classificada como quente (85% ou mais), morna (70% a 85%), fria (40% a 70%) ou gelada (menos de 40%). Só aulas frias e geladas são indicadas para promoção; aulas quentes indicam demanda para uma nova turma.", "Novo"],
].map(([id, titulo, texto, situacao]) => ({ id, titulo, texto, situacao }));

// ---------------------------------------------------------------- rastreabilidade (de fluxos.json)
const fluxosDe = (id) => FLUXOS.filter(f => f.requisitos.includes(id)).map(f => f.numero);
const semFluxo = [...RF, ...RN].filter(r => fluxosDe(r.id).length === 0).map(r => r.id);
const desconhecidos = [...new Set(FLUXOS.flatMap(f => f.requisitos))]
  .filter(id => ![...RF, ...RN, ...RNF].some(r => r.id === id));
if (semFluxo.length || desconhecidos.length) {
  console.error("Rastreabilidade inconsistente:", { semFluxo, desconhecidos });
  process.exit(1);
}
const linhaRastro = (r) => [r.id, r.titulo, fluxosDe(r.id).join(", ")];

// ---------------------------------------------------------------- documento
const capa = [
  new Paragraph({ spacing: { before: 1800, after: 200 }, alignment: AlignmentType.CENTER, children: [t("Portal da Dança", { bold: true, size: 48, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [t("Sistema de gestão da escola — requisitos, fluxos e protótipo", { size: 26, color: "444444" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 900 }, children: [t("Relatório final — versão 1.0", { bold: true, size: 24 })] }),
  p([t("Instituição: ", { bold: true }), t("FATEC Rubens Lara")]),
  p([t("Curso: ", { bold: true }), t("Análise e Desenvolvimento de Sistemas")]),
  p([t("Disciplina: ", { bold: true }), t("Projeto Integrador em Análise e Desenvolvimento de Sistemas I — 2º semestre de 2026")]),
  p([t("Professora orientadora: ", { bold: true }), t("Rosemeire Cardozo Vidal")]),
  p([t("Licença: ", { bold: true }), t("MIT — uso gratuito")]),
  p([t("Empresa: ", { bold: true }), t("Portal da Dança")]),
  p([t("Equipe:", { bold: true })], { spacing: { before: 120, after: 60 } }),
  ...ALUNOS.map((a, i) => p(`${i + 1}. ${a}`, { spacing: { after: 20 }, indent: { left: 360 } })),
  p([t("Versão 1.0: ", { bold: true }), t("10/11/2026")], { spacing: { before: 300 } }),
  quebra(),
];

const historico = [
  h1("Histórico de revisões"),
  tabela(["Versão", "Data", "Alterações"], [
    ["1.0", "10/11/2026", "Versão final, revisada após as observações da professora sobre a versão preliminar (requisitos RF01–RF16, RNF01–RNF08 e RN01–RN07): RF05 substituído pela consulta da agenda (a escola não tem catraca); forma de pagamento separada da origem (RF08/RN02); RF17–RF21 e RN08–RN12 incluídos; salário dos professores calculado por aluno inscrito na matrícula (RF13, RN07, RN16), com matrícula com data de início e fim (RF21); novos RF22–RF25 e RN13–RN17, incluindo a consulta de frequência e oportunidades de promoção; fluxogramas corrigidos, numerados de 00 a 17; protótipo em Django, implantado como serviço, e verificação (seções 6 e 7)."],
  ], [1100, 1500, 7038]),
  espaco(),
];

const s1 = [
  h1("1. Introdução"),
  corpo("O objetivo deste documento é formalizar os requisitos de negócio, funcionais e não funcionais derivados da investigação realizada com a Portal da Dança, considerando as necessidades identificadas no controle de alunos, matrículas, aulas, presença, faltas e movimentações financeiras."),
  corpo("A Portal da Dança é uma escola de dança que atualmente controla a presença e as faltas dos alunos e as movimentações financeiras por meio de planilhas do Excel. O controle financeiro é atualizado diariamente e envolve diferentes categorias de entradas e saídas. O fechamento mensal depende da análise dessas movimentações para comparar valores recebidos e gastos e acompanhar o saldo da escola."),
  corpo("O propósito do sistema é centralizar os controles hoje mantidos em várias planilhas, tornando o registro e a consulta das informações mais rápidos e práticos para o responsável pela Portal da Dança. Esta versão também descreve o protótipo desenvolvido e a verificação feita sobre ele."),
  h2("1.1 Contexto acadêmico e projeto social"),
  corpo("Este sistema é um projeto da disciplina Projeto Integrador em Análise e Desenvolvimento de Sistemas I, do curso de Análise e Desenvolvimento de Sistemas da FATEC Rubens Lara, desenvolvido no 2º semestre de 2026 sob a orientação da Professora Rosemeire Cardozo Vidal."),
  corpo("Além de atender à Portal da Dança, o projeto tem caráter social: é um software produzido na FATEC e devolvido à sociedade. Pequenas escolas de dança, estúdios e outros negócios que organizam aulas por turmas costumam depender de planilhas e não têm acesso a sistemas de gestão pagos. Por isso o código é aberto e distribuído sob a licença MIT, que permite usar, copiar, modificar e distribuir o sistema gratuitamente, inclusive em atividades comerciais, desde que o aviso de direitos autorais e de licença seja mantido. Como prevê a própria licença, o software é oferecido sem garantia."),
  corpo("O sistema foi organizado para poder ser adaptado por outras escolas e empresas, do estado, do país ou de qualquer lugar: os módulos são separados, as regras de negócio estão documentadas e testadas, e itens como as salas, as modalidades, o horário de funcionamento e os limites da consulta de oportunidades são configuráveis. Novas versões poderão ampliar o uso, por exemplo com perfis de acesso por tipo de usuário e suporte a mais de uma unidade."),
];

const s2 = [
  h1("2. Metodologia de levantamento de informações"),
  h2("2.1 Técnicas utilizadas"),
  corpo("Foram utilizadas as seguintes técnicas de coleta de dados:"),
  bullet("Entrevista semiestruturada com o responsável pela escola, para compreender o funcionamento atual dos controles."),
  bullet("Observação do processo de utilização das planilhas, acompanhando o registro de pagamentos, despesas e presenças."),
  bullet("Análise, com autorização do responsável, das planilhas utilizadas pela escola, para identificar as informações e estruturas que precisam ser consideradas no sistema."),
  h2("2.2 Participantes da entrevista"),
  corpo("A entrevista foi realizada pelos integrantes da equipe Rodrigo Conde Attanasio e Cauêt da Silva com o responsável pela administração da Portal da Dança, que utiliza e gerencia os controles atualmente feitos no Excel. A entrevista ocorreu via WhatsApp, pois o responsável só tinha disponibilidade após as 22h, o que também impossibilitou uma visita ao local."),
  h2("2.3 Roteiro da entrevista, observação e análise de documentos"),
  corpo("As questões que orientaram a investigação e os esclarecimentos complementares foram:"),
  ...["Como é realizado atualmente o controle de presença e faltas dos alunos?",
    "Como são registradas as entradas e saídas financeiras e com que frequência?",
    "Quais formas de pagamento são aceitas?",
    "Como são registradas as mensalidades e as receitas provenientes de eventos?",
    "Como são registradas as contas e demais despesas da escola?",
    "Como é realizado o balanço financeiro no final do mês?",
    "Como é calculada a remuneração dos professores?",
    "Como as aulas são agendadas e organizadas por sala, modalidade e horário?",
    "Quantas salas existem e qual é a capacidade de cada uma?",
    "Quais modalidades têm maior procura?",
    "Quais dificuldades ou problemas são encontrados no uso das planilhas do Excel?",
    "Quais informações o responsável precisa consultar com maior frequência?"].map(bullet),
  corpo("Também foi observado o processo atual de utilização das planilhas, incluindo as etapas de registro de pagamentos, despesas e presenças que dependem desses arquivos. As planilhas foram analisadas para identificar os tipos de informações armazenadas e a forma como os dados são organizados."),
];

const s3 = [
  h1("3. Compreensão do negócio"),
  h2("3.1 Descrição da empresa"),
  p([t("Nome: ", { bold: true }), t("Portal da Dança")]),
  p([t("Ramo de atuação: ", { bold: true }), t("atividades de recreação e lazer.")]),
  p([t("Alunos: ", { bold: true }), t("aproximadamente 250.")]),
  p([t("Funcionamento: ", { bold: true }), t("todos os dias, das 18h às 22h.")]),
  p([t("Estrutura: ", { bold: true }), t("duas salas, com capacidade informada de até 40 alunos por sala.")]),
  p([t("Modalidades: ", { bold: true }), t("forró, zouk, salsa, bachata, sertanejo e samba rock; forró e zouk são as mais procuradas.")]),
  h2("3.2 Problema identificado"),
  corpo("A escola controla presenças e faltas dos alunos e registra os custos em planilhas do Excel. As movimentações ocorrem diariamente, e o fechamento mensal depende da comparação entre valores recebidos e gastos para acompanhar o saldo. O controle de presença e faltas é feito sem catraca: a escola não possui sistema de catraca nem controle automatizado de entrada e saída."),
  corpo("A principal dificuldade identificada é a dependência de várias planilhas e a necessidade de inserir dados manualmente. Isso torna os lançamentos mais lentos e pode dificultar a organização e a consulta das informações. A solução deverá centralizar os controles e tornar o registro e a consulta mais rápidos e práticos."),
  h2("3.3 Objetivos do sistema"),
  corpo("A solução proposta é um sistema centralizado para a gestão da escola, reunindo o controle de alunos, professores, aulas, horários, matrículas, presença, faltas e movimentações financeiras. O sistema deve permitir registrar entradas e saídas, controlar custos, calcular o salário dos professores a partir dos alunos inscritos em suas aulas, acompanhar mensalidades, consultar o saldo e visualizar o balanço mensal. Também deve permitir agendar aulas previamente, matricular alunos nas aulas respeitando a capacidade das salas e registrar presenças e faltas, sem exigir matrícula para a participação. Para o proprietário, deve mostrar quais aulas são mais frequentadas e onde há vagas ociosas que justifiquem promoções. A solução deve priorizar rapidez, praticidade, organização, segurança e facilidade de consulta."),
];

const s4 = [
  h1("4. Levantamento de requisitos"),
  h2("4.1 Requisitos funcionais (RF)"),
  ...RF.flatMap(requisito),
  h2("4.2 Requisitos não funcionais (RNF)"),
  ...RNF.flatMap(requisito),
  h2("4.3 Requisitos de negócio (RN)"),
  ...RN.flatMap(requisito),
  h2("4.4 Exemplo do cálculo do salário (RN07 e RN16)"),
  corpo("Uma professora com valor de R$ 25,00 por aluno inscrito dá Forró às segundas (20 inscritos) e às sextas (15 inscritos, dos quais 5 também fazem a aula de segunda). No mês, são 20 + 15 = 35 inscrições, e o salário é 35 × R$ 25,00 = R$ 875,00. Os 5 alunos que fazem as duas aulas contam duas vezes, porque cada inscrição é uma vaga ocupada na turma. Se um aluno faltar a todas as aulas do mês, o valor não muda; se um aluno avulso, sem matrícula, frequentar a aula, ele não entra no cálculo."),
  h2("4.5 Consulta de frequência e oportunidades (RF25 e RN17)"),
  corpo("A consulta é feita a partir das chamadas e matrículas já registradas, sem nenhum dado novo. A ocupação usa a presença, e não a inscrição, porque um aluno inscrito que não comparece não ocupa lugar na sala. Sistemas de gestão de academias e estúdios medem a utilização das aulas da mesma forma e consideram saudável a faixa de 70% a 85%."),
  tabela(["Temperatura", "Ocupação", "Sugestão exibida"], [
    ["Quente", "85% ou mais", "Não fazer promoção; avaliar abrir outra turma da modalidade ou rever o valor."],
    ["Morna", "70% a 85%", "Manter; promoções só pontuais."],
    ["Fria", "40% a 70%", "Promoção leve no horário: aula experimental, “traga um amigo” ou pacote."],
    ["Gelada", "menos de 40%", "Promoção forte, ou mudar dia e horário, ou juntar com outra turma."],
  ], [1700, 1900, 6038]),
  espaco(),
  corpo("Além da temperatura, a sugestão considera três sinais. A tendência compara a média de presentes da segunda metade do período com a da primeira; uma queda de 15% ou mais gera um aviso, mesmo em aulas mornas ou quentes. A frequência é a proporção de presenças entre os registros da chamada; abaixo de 70%, o problema indicado é engajamento, e não vaga. Os alunos avulsos (RN08) que somam 20% ou mais das presenças indicam demanda que pode virar matrícula."),
  corpo("Exemplo: uma aula na sala de 40 lugares com 10 aulas no período e 160 presenças tem média de 16 presentes e ocupação de 40%, ficando na faixa fria, com cerca de 24 lugares vazios por aula. Se a média das últimas 5 aulas for 12 e a das 5 primeiras for 20, a tendência é de queda de 40%, e o sistema avisa que a aula está esfriando."),
];

const RNF_LINHAS = RNF.map(r => [r.id, r.titulo, "Todos os fluxos"]);
const s5 = [
  h1("5. Rastreabilidade dos requisitos e fluxos"),
  corpo("As tabelas relacionam cada requisito aos fluxos que o atendem. Os números são os mesmos das abas do arquivo de fluxogramas (Portal_da_Danca_Fluxogramas_v1.0), numerados de 00 a 17 sem lacunas. Esta seção é gerada a partir do próprio arquivo de fluxogramas, o que garante que os dois documentos não divergem."),
  h2("5.1 Fluxos"),
  tabela(["Nº", "Fluxo", "Situação"], FLUXOS.map(f => [f.numero, f.titulo, f.situacao]), [800, 6638, 2200]),
  espaco(),
  h2("5.2 Requisitos funcionais"),
  tabela(["Código", "Requisito", "Fluxo(s)"], RF.map(linhaRastro), [1200, 5938, 2500]),
  espaco(),
  h2("5.3 Requisitos de negócio"),
  tabela(["Código", "Requisito", "Fluxo(s)"], RN.map(linhaRastro), [1200, 5938, 2500]),
  espaco(),
  h2("5.4 Requisitos não funcionais"),
  tabela(["Código", "Requisito", "Fluxo(s)"], RNF_LINHAS, [1200, 5938, 2500]),
  espaco(),
  corpo("Os requisitos não funcionais são transversais: devem ser considerados na implementação de todos os fluxos. O RNF03 tem fluxo próprio (00 — Acesso ao sistema) e o RNF04 aparece também no fluxo 16 (auditoria)."),
];

const s6 = [
  h1("6. Protótipo desenvolvido"),
  corpo("O protótipo é uma aplicação web em Python 3.14 e Django 6.1, com banco de dados SQLite, acessada pelo navegador. Ele implementa todos os requisitos funcionais e de negócio desta versão. Os gráficos são feitos em HTML e CSS, sem bibliotecas externas."),
  h2("6.1 Módulos"),
  tabela(["Módulo", "O que faz", "Requisitos"], [
    ["Acesso", "Login obrigatório, logout e registro de cada acesso.", "RF22, RF24, RNF03"],
    ["Alunos", "Cadastro, busca, atualização; histórico de presenças, aulas e mensalidades do aluno.", "RF01, RF02"],
    ["Professores", "Cadastro, consulta e atualização, com o valor por aluno inscrito e o salário estimado do mês.", "RF17"],
    ["Aulas", "Modalidades, salas, agenda semanal com filtros, validação de horário e conflitos, matrícula com histórico, chamada por data com aluno avulso e consulta de presenças e faltas.", "RF03–RF05, RF18–RF21, RN08–RN10, RN13–RN15"],
    ["Financeiro", "Entradas, saídas, mensalidades, despesas, salários por matrícula, movimentações, saldo, balanço mensal e correção de lançamentos.", "RF06–RF16, RF23, RN01–RN07, RN11, RN12, RN16"],
    ["Consultas", "Para o proprietário: aulas mais frequentadas, mapa de calor da agenda por dia e horário, temperatura de cada aula, presenças por semana, ocupação por modalidade e sugestões de promoção.", "RF25, RN17"],
    ["Administração", "Lista de usuários e auditoria (quem acessou, de qual IP, logins, falhas e alterações), visível só para a equipe.", "RF24, RNF04"],
    ["Documentação", "Resumo da revisão e tabelas de análise dentro do próprio sistema.", "—"],
  ], [1700, 5438, 2500]),
  espaco(),
  h2("6.2 Como executar"),
  bullet("Instalar as dependências: python -m venv .venv e .venv/bin/pip install -r requirements.txt."),
  bullet("Criar o banco: .venv/bin/python manage.py migrate."),
  bullet("Dados de demonstração: .venv/bin/python manage.py popular_demo. A senha do usuário criado vem da variável DJANGO_DEMO_SENHA ou é gerada e exibida uma única vez."),
  bullet("Executar em desenvolvimento: .venv/bin/python manage.py runserver 0.0.0.0:3010 e acessar pelo navegador."),
  bullet("Executar no servidor da escola: o sistema roda com o gunicorn como serviço do systemd (escoladedanca.service), iniciado junto com o servidor, na porta 3010. A configuração (modo de depuração desligado, endereços aceitos, retenção da auditoria) fica no arquivo .env, e os arquivos de estilo são servidos pelo WhiteNoise depois de .venv/bin/python manage.py collectstatic."),
  bullet("Relatório de acessos: .venv/bin/python manage.py relatorio_acessos."),
];

const v = VER;
const s7 = [
  h1("7. Verificação"),
  corpo(`A verificação foi executada em ${v.data}, sobre o código do protótipo e sobre este relatório.`),
  h2("7.1 Testes automatizados"),
  corpo(`A suíte tem ${v.testes_total} testes automatizados, e todos passaram (${v.testes_resultado}). Cada teste indica no nome ou na descrição o requisito que verifica.`),
  tabela(["Módulo", "Testes", "O que verificam"], v.testes_por_modulo.map(m => [m.modulo, String(m.testes), m.verifica]), [1800, 1100, 6738], { centro: [1] }),
  espaco(),
  h2("7.2 Análise estática de segurança"),
  corpo(`O código foi analisado com o Semgrep (conjuntos de regras p/secrets, p/django e p/python): ${v.semgrep}. Também foi confirmado que o banco está de acordo com os modelos (${v.migracoes}).`),
  h2("7.3 Consistência entre relatório, fluxogramas e sistema"),
  bullet(`Todos os ${RF.length} requisitos funcionais e ${RN.length} requisitos de negócio aparecem em pelo menos um fluxo (verificação automática ao gerar este relatório).`),
  bullet("Todos os requisitos citados nos fluxogramas existem neste relatório."),
  bullet(`Os ${FLUXOS.length} fluxos estão numerados de 00 a 17, sem lacunas (na versão preliminar faltavam 05, 07 e 11).`),
  bullet("O arquivo .drawio foi validado: cada seta liga duas caixas existentes."),
  h2("7.4 Problemas encontrados e corrigidos durante a verificação"),
  tabela(["Problema", "Correção"], v.problemas.map(x => [x.problema, x.correcao]), [4819, 4819]),
  espaco(),
  h2("7.5 Atendimento às observações da professora"),
  tabela(["Observação", "Como foi atendida"], [
    ["Adicionar ou remover aulas e horários, cadastro de professores, quantidade de alunos por aula", "RF17–RF21 e fluxos 02, 03, 04, 05 e 14."],
    ["Regras para os alunos: matrícula, pagamento em dia, tolerância, taxa, afastamento, exame médico", "RN08: a escola não adota essas regras; o sistema não bloqueia alunos e aceita alunos avulsos."],
    ["RF05 “controle de entrada e saída de alunos” (a escola não tem catraca)", "Substituído pela consulta da agenda de aulas (fluxo 14)."],
    ["Classificação das entradas misturava forma de pagamento e origem", "RF08 e RN02 separam as duas classificações; ambas são obrigatórias."],
    ["Como é calculado o salário dos professores", "RF13, RN07 e RN16: por aluno inscrito na matrícula, com exemplo na seção 4.4 e fluxo 11."],
  ], [4819, 4819]),
  espaco(),
];

const s8 = [
  h1("8. Pendências e limitações"),
  bullet([t("Valor por aluno: ", { bold: true }), t("a escola ainda não informou o valor pago por aluno inscrito. O sistema permite definir esse valor em cada professor; ele precisa ser confirmado com o responsável.")]),
  bullet([t("Validação com a escola: ", { bold: true }), t("os requisitos novos desta versão (RF22–RF25 e RN13–RN17) foram definidos pela equipe a partir do que o sistema precisa garantir e devem ser confirmados com o responsável pela Portal da Dança.")]),
  bullet([t("Troca de professor de uma aula: ", { bold: true }), t("o salário de meses anteriores é recalculado com o professor atual da aula. Se o professor de uma turma mudar, o cálculo de meses passados deve ser conferido com os pagamentos já registrados.")]),
  bullet([t("Limites da consulta de oportunidades: ", { bold: true }), t("as faixas de temperatura (RN17) seguem referências de mercado para academias e estúdios. Devem ser validadas com a escola, assim como a lotação confortável de cada sala em dança a dois, que pode ser menor que os 40 lugares informados. Os limites são configuráveis.")]),
  bullet([t("Uso por outras escolas: ", { bold: true }), t("o sistema foi validado apenas com o cenário da Portal da Dança. Outra escola que o adote deve revisar as regras configuráveis (salas, modalidades, horário, valor por aluno e limites da consulta) e as obrigações da LGPD no seu próprio uso.")]),
  bullet([t("Implantação: ", { bold: true }), t("o sistema já roda como serviço (gunicorn e systemd), com modo de depuração desligado e chave secreta fora do código. Ainda falta HTTPS: o acesso é por HTTP na rede da escola, e para acesso pela internet é necessário um certificado e um proxy reverso.")]),
];

const doc = new Document({
  creator: "Equipe Portal da Dança",
  title: "Portal da Dança — Relatório final, versão 1.0",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 30, bold: true, color: AZUL },
        paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 24, bold: true, color: "222222" },
        paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 567, hanging: 283 } } } }] }] },
  sections: [
    { properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, bottom: 1134, left: 1134, right: 1134 } } },
      children: capa },
    { properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, bottom: 1134, left: 1134, right: 1134 },
        pageNumbers: { start: 2 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [t("Portal da Dança — Relatório final v1.0   ·   ", { size: 16, color: "777777" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "777777" })] })] }) },
      children: [...historico, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8] },
  ],
});

Packer.toBuffer(doc).then(buf => {
  const destino = path.join(AQUI, "Relatorio_Portal_da_Danca_v1.0.docx");
  fs.writeFileSync(destino, buf);
  console.log("Gerado:", destino, `(${RF.length} RF, ${RNF.length} RNF, ${RN.length} RN, ${FLUXOS.length} fluxos)`);
});

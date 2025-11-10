# EduGit – Plug-in do Moodle simulando Github
### Especificação e Protótipo
Grupo nº X

**Integrantes**
Daniel Ferreira Alves - dandastico.bsb@gmail.com

**Prof. Orientador**
MSc. Edilberto M. Silva - prof.edilberto.silva@gmail.com

**11/2025**

## 1. INTRODUÇÃO
O objetivo deste documento é coletar, analisar e deifinir as necessiades e recursos de alto nível do projeto do **EduGit** que tem como objetivo organizar e gerenciar códigos dos professores e alunos que foram criados para as atividades acadêmicas pelo Moodle.

O projeto EduGit também visa criar uma plataforma de testes do código dos alunos, seguindo os casos de uso estabelecidos pelos professores, para acelerar a correção das atividades e a entrega do feedback para os alunos.

O EduGit é um sistema de controle de versão, como o Git, por onde os alunos conseguem baixar os códigos desenvolvidos pelos professores para o ambiente de programação local. Ao realizar as atividades propostas pelos professores, os alunos conseguem enviar suas soluções para o plug-in do Moodle que será desenvolvido, um repositório na nuvem que funcionará como uma versão simplificada do GitHub.

Além das funções de sistema de controle de versão, o EduGit permite ao professor cria pequenos testes unitários para testar o código dos alunos. Com esses testes, os alunos tem a opção de experimentar suas soluções antes de enviar o código para a correção do professor.

## 2. DESCRIÇÃO DO PROJETO

### 2.1. Título do Projeto
EduGit

### 2.2. Objetivos de Alto Nível
- PARA alunos e professores de programação da Faculdade SENAC-DF 
- QUE necessitam de uma forma mais eficiente e organizada de gerenciar o envio e correção de atividades práticas de código, O EduGit É um plug-in para Moodle que atua como um sistema de controle de versão educacional,
- DIFERENTEMENTE DO GitHub tradicional que é genérico e não integrado com correção automática, 
- NOSSO PRODUTO oferece integração nativa com o Moodle, testes unitários automáticos configurados pelos professores e comando de envio simplificado via terminal, inspirado no modelo do CS50 de Harvard.
- QUANDO precisa estar pronto? A primeira versão funcional deve estar implementada até o final do semestre letivo vigente (27/11/2025).
- QUANTO é a previsão de custos? Investimento inicial estimado em R$ 4.000 considerando mão de obra especializada.

## 3. ESCOPO DO PROJETO
Funcionalidades Principais:
- Envio por Terminal: Comandos personalizados como "edugit enviar" para submissão das atividades
- Testes Automatizados: Execução de testes unitários configurados pelos professores
- Feedbak imediato: retorno automático sobre correção dos exercícios
- Integração ao Moodle: Sincronização com atividades e notas do Moodle
- Repositório central: Armazenamento seguro dos códigos dos alunos
- Templates Download: Distribuição de materiais base via comando terminal

Limitações:
- Versão 1.0: Suporte inicial apenas para Python
- Correção: Apenas testes automáticos - sem análise qualitativa de código (não verifica se segue padrões como "Código Limpo")
- Trabalho individual: Sem recursos para trabalhos em grupo
- Histórico: Versionamento básico, sem histórico detalhado de commits
- Interface: Foco no terminal, interface gráfica mínima

### 3.1. Escopo do Produto (Requisitos Funcionais)
- RF01 - Manter cadastro de usuário
  - RF01.1 - Consultar Usuário
  - RF01.2 - Cadastrar Usuário
  - RF01.3 - Validar Código
    - Gerar código, enviar e-mail, validar código, reenviar código
  - RF01.4 - Editar Usuário
  - RF01.5 - Excluir Usuáario

- RF02 - Gerenciar login do usuário
  - RF02.1 - Validar Credencial
  - RF02.2 - Redefinir Senha (esquecer a senha)

- RF03 - Gerenciar atividades
  - RF03.1 - Criar Atividade
  - RF03.2 - Editar Atividade
  - RF03.3 - Excluir Atividade
  - RF03.4 - Publicar/Ocultar Atividade
  - RF03.5 - Definir Prazo de Entrega
  - RF03.6 - Configurar Template Inicial
  - RF03.7 - Associar Testes Unitários à Atividade

- RF04 - Gerenciar Submissões de Código
  - RF04.1 - Enviar Código via Terminal
  - RF04.2 - Validar Formato do Código
  - RF04.3 - Listar Submissões por Aluno
  - RF04.4 - Download do Código Subetido

- RF05 - Executar Testes Automatizados
  - RF05.1 - Configurar Testes Unitários
  - RF05.2 - Executar Testes no Servidor
  - RF05.3 - Gerar Relatórios de Testes
  - RF05.4 - Definir Casos de Testes
  - RF05.5 - Calcular Pontuação Automática

### 3.2. Escopo do projeto (Requisitos do Projeto)

## 4. DIAGRAMA DE CASO DE USO


## 5. MODELO ENTIDADE E RELACIONAMENTO (MER)


## 6. ESPECIFICAÇÃO DOS REQUISITOS


## 7. DIAGRAMA DE ATIVIDADES
# Abertura de Chamados

Programa interno da Cadari para a equipe pedir suporte (Revit, Dynamo, AutoCAD, Office e outros), fazer a triagem desses pedidos e transformar cada chamado em tarefa no FlowUp.

Versão atual: **2.3.0** (outubro de 2026). O que mudou em cada versão está no [CHANGELOG.md](CHANGELOG.md).

## Como funciona

1. **Novo chamado.** Na mesma tela a pessoa preenche o pedido (nome, categoria, assunto, tema, descrição, imagem opcional) e, se já souber, o responsável, o prazo e o status. O programa grava o chamado e devolve o protocolo (C001, C002...).
2. **Tarefa no FlowUp.** Com responsável definido, a tarefa é criada no quadro CHAMADOS e PROTOCOLOS, já com a descrição do chamado. Sem responsável, o chamado aguarda triagem na aba "Chamados", e a tarefa é criada quando alguém escolher o responsável e salvar.
3. **Acompanhamento.** Na aba "Chamados" ficam a lista com filtros e o painel de detalhes: salvar alterações (atualiza a tarefa) e excluir (apaga o chamado e a tarefa). Os status são os mesmos do quadro do FlowUp; para encerrar, escolha Finalizadas e salve.
5. **Uso.** Tema claro ou escuro e zoom (Ctrl + rolagem do mouse) ficam salvos por pessoa. Nas listas, a rolagem do mouse e as letras do teclado escolhem o item.
4. **Equipe.** A cada abertura, a lista de pessoas é atualizada com os usuários ativos do FlowUp.

Todos os usuários trabalham sobre os mesmos dados, que ficam numa pasta da rede. O executável só lê e grava nessa pasta e chama a API do FlowUp.

## Onde fica cada coisa

| O quê | Onde | Vai para o GitHub? |
|---|---|---|
| Código, imagens, testes e documentação | este repositório | Sim |
| Banco de chamados, lista da equipe, `config.json` com o token do FlowUp, anexos e logs | `Z:\Biblioteca\Padronização\Cadari\Processos BIM\Formulário de bugs\Banco de dados` | **Não, nunca** |
| Executável usado pela equipe | gerado em `dist\` e copiado para a rede e para as áreas de trabalho | Não (pode ser anexado em uma Release) |

## Estrutura do repositório

```
Bugs.py                         ponto de entrada: tela inicial e carga dos dados (nome histórico)
janelas.py                      telas (carregamento, novo chamado, lista e detalhes)
tema.py                         identidade visual: cores, fonte e componentes
servico.py                      regras da integração com o FlowUp (criar, atualizar, excluir)
equipe.py                       sincronização da lista da equipe com o FlowUp
verificacao.py                  verificação do computador (rede, permissões, FlowUp)
database.py                     leitura e gravação no banco SQLite
flowup_api.py                   chamadas à API do FlowUp
config.py                       versão, pasta de dados, leitura do config.json e log
Abertura de Chamados.spec       receita do executável (PyInstaller)
config.example.json             modelo do config.json, sem token
requirements.txt                bibliotecas Python usadas
matriz/                         imagens das telas, ícone e tela de abertura
ferramentas/diagnostico_flowup.py   verificação da integração com o FlowUp (somente leitura)
testes/                         testes automáticos (não acessam rede nem FlowUp)
docs/                           documentação detalhada
```

## Começo rápido para quem vai mexer no código

Pré-requisitos: Windows, Python 3.12 e acesso ao drive Z:.

```bat
git clone <endereço do repositório>
cd <pasta clonada>
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m unittest discover -s testes -v
```

Para abrir o programa sem mexer nos dados reais, aponte para uma cópia da pasta de dados (passo a passo em [docs/desenvolvimento-e-distribuicao.md](docs/desenvolvimento-e-distribuicao.md)):

```bat
set CHAMADOS_PASTA_DADOS=C:\temp\chamados_teste
python Bugs.py
```

Para gerar o executável:

```bat
pyinstaller --clean --noconfirm "Abertura de Chamados.spec"
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/arquitetura.md](docs/arquitetura.md) | Como o programa está organizado, telas, banco de dados e regras da integração com o FlowUp |
| [docs/configuracao.md](docs/configuracao.md) | `config.json`, token do FlowUp, IDs, lista da equipe e opções dos formulários |
| [docs/desenvolvimento-e-distribuicao.md](docs/desenvolvimento-e-distribuicao.md) | Ambiente de desenvolvimento, testes, compilação, distribuição do exe e publicação no GitHub |
| [docs/manutencao-e-problemas.md](docs/manutencao-e-problemas.md) | Diagnóstico, erros comuns e o que fazer, logs, banco de dados, backup e histórico de incidentes |

## Regras para o projeto continuar saudável

- Token, senha e caminho de rede não entram no código. Ficam no `config.json` da pasta de dados ou no `config.py`.
- `chamados.db`, `nomes_equipe.csv` e `config.json` nunca vão para o GitHub. O `.gitignore` já bloqueia esses arquivos.
- Teste com uma cópia dos dados antes de distribuir uma versão nova.
- Toda versão nova: aumentar `VERSAO` no `config.py`, registrar no `CHANGELOG.md`, compilar e substituir o exe de todos.
- Se a integração com o FlowUp parar, rode `python ferramentas\diagnostico_flowup.py` antes de mexer no código. Ele aponta token vencido, endereço da API alterado, status ou pessoas que não existem mais no FlowUp e chamados que ficaram sem tarefa.

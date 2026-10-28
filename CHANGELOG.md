# Histórico de versões

Formato: a versão mais nova primeiro. Cada versão distribuída deve ter uma entrada aqui e o mesmo número em `VERSAO` no `chamados/config.py`.

## 2.3.0 (outubro de 2026)

### Organização do código
- Código movido para o pacote `chamados/` (núcleo) e `chamados/interface/` (telas). O antigo `janelas.py` foi dividido em uma tela por arquivo, e as categorias do formulário foram para `chamados/categorias.py`.
- Ponto de entrada renomeado de `Bugs.py` para `main.py`; a pasta `matriz/` passou a se chamar `assets/` e guarda só as imagens usadas pelo programa.
- Nenhuma mudança de comportamento.

### Adicionado
- Verificação do computador (`verificacao.py`): pasta da rede, permissão de gravação, banco, lista da equipe, configuração e conexão com o FlowUp. Roda sozinha na abertura e pelo botão "Verificar computador" no topo, com relatório que pode ser copiado para um chamado de Suporte TI.
- Aviso na tela de carregamento quando uma etapa passa de 15 segundos.

### Corrigido
- A abertura podia ficar parada na tela de carregamento por mais de um minuto em computadores sem acesso ao FlowUp (duas consultas esperando 30 s cada). Agora a conexão é testada com limite de 8 s e, se falhar, o programa abre usando a lista da equipe e os status salvos.
- A tela de abertura do PyInstaller é fechada logo no início, para não esconder mensagens de erro do Windows; falhas antes da janela abrir aparecem numa caixa de diálogo e vão para o log.
- O log não cria mais a pasta de dados quando ela não existe.

## 2.2.0 (outubro de 2026)

### Alterado
- Status iguais aos do quadro do FlowUp (Novas, Em andamento, Pendência Interna, Finalizadas), lidos do FlowUp a cada abertura. Os status antigos do banco são convertidos automaticamente (Não visto e Visto: Novas; Em execução: Em andamento; Solucionado e Fechado: Finalizadas; Não solucionado: Pendência Interna). O botão "Fechar chamado" saiu: basta escolher Finalizadas e salvar.
- Nenhum texto em itálico; destaques em negrito.
- Tema escuro quase preto em toda a interface (topo, rodapé, tela de carregamento, calendário). A escolha de tema fica salva por pessoa.
- Calendários com a fonte, o tamanho e as cores dos demais campos, nos dois temas.

### Adicionado
- Listas de seleção: a rolagem do mouse troca o item, as setas sobem e descem e digitar uma letra pré-seleciona o primeiro nome com essa inicial (letras seguidas formam o começo do nome; a mesma letra repetida passa para o próximo).
- Os campos "Software" e "Ferramenta" passaram a se chamar "Categoria" e "Assunto" (no formulário, no filtro e na descrição da tarefa no FlowUp). Nova categoria "Suporte TI", com os assuntos: Programas internos, Sugestão de automação, Instalação e atualização, Acesso e permissões, Rede e VPN, FlowUp, Computador e periféricos, E-mail e comunicação, Licenças e Outros.
- Zoom com Ctrl + rolagem do mouse (ou Ctrl + / Ctrl - ; Ctrl 0 volta a 100%), de 80% a 160%, salvo por pessoa.

## 2.1.0 (outubro de 2026)

### Alterado
- Nova interface com a identidade visual da Cadari (paleta, Franklin Gothic Book, marca, títulos com listra para tópicos, rodapé com linhas diagonais) e tema claro e escuro.
- Tudo em uma janela: aba "Novo chamado" (abertura e encaminhamento na mesma tela) e aba "Chamados" (lista com filtros e painel de detalhes).
- Tela de carregamento nova, com a etapa atual, a porcentagem e barra de progresso. A tela do PyInstaller (`matriz/tela_abertura.png`) também foi refeita.
- A descrição do chamado (e as observações da triagem) agora vai para a descrição da tarefa no FlowUp, em vez do campo de comentários que a API ignorava.
- Exportação para CSV usa ponto e vírgula, para abrir direto no Excel em português.

### Adicionado
- Lista da equipe sincronizada com os usuários ativos do FlowUp a cada abertura (`equipe.py`). Pode ser desligada com `"sincronizar_equipe": false` no `config.json`.
- Excluir chamado (também exclui a tarefa no FlowUp e o anexo).
- `servico.py` com as regras da integração separadas das telas, e `tema.py` com cores e componentes.
- Marca em `matriz/marca_policromia.png` e `matriz/marca_negativa.png`.

## 2.0.0 (outubro de 2026)

Versão de recuperação da integração com o FlowUp e de preparação do projeto para o GitHub. Detalhes do incidente em [docs/manutencao-e-problemas.md](docs/manutencao-e-problemas.md#histórico-de-incidentes).

### Corrigido
- Criação e atualização de tarefas: o programa passou a usar o endereço atual da API do FlowUp (`https://api.flowup.me/v1/Task/...`). O endereço antigo foi desativado pela FlowUp entre junho e agosto de 2026.
- Nova tentativa depois de falha: a decisão entre criar e atualizar a tarefa passou a olhar o número da tarefa (`flowup_task_id`), e não o responsável. Chamados que ficaram sem tarefa (C032 e C033) passam a ser criados ao salvar de novo.
- IDs de status: os valores fictícios (12345 a 12348) foram trocados pelos status reais do quadro. "Não solucionado" vai para Pendência Interna; "Solucionado" e "Fechado" vão para Finalizadas; "Em execução" vai para Em andamento.
- Fechar Chamado agora leva a tarefa para Finalizadas no FlowUp e avisa se não conseguir (antes usava um ID de status inexistente e não conferia a resposta).
- Anexos: as imagens eram copiadas para a pasta temporária do executável e se perdiam ao fechar o programa. Agora ficam em `Banco de dados\anexos`, com caminho relativo no banco.
- Lista "Ver Todos os Chamados": o primeiro nome em ordem alfabética sumia dos filtros e da janela de detalhes.
- Tela de carregamento ficava girando para sempre quando o Z: não estava acessível. Agora o programa abre e mostra o erro.
- Respostas de erro da API apareciam como página HTML inteira na mensagem. Agora a mensagem é curta e o detalhe vai para o log.

### Alterado
- Token e IDs do FlowUp saíram do código e foram para `config.json` na pasta de dados. Trocar token, quadro, status ou seguidores não exige mais recompilar.
- Seguidores fixos das tarefas: só Renata (ID 10). O ID 31, que era do Paulo, passou a ser do Lucas Gomes no FlowUp e foi retirado.
- `nomes_equipe.csv` sincronizado com os usuários ativos do FlowUp: ID 31 virou Lucas Gomes, ID 68 virou Bruno Constantino; saíram Paloma, Fernanda Marques e Pedro Antônio Ribeiro Teixeira; entraram Fernando, Ana Elisa, Joyce Sabino, Marinês Viana e Pedro Oliveira. Chamados antigos com responsável "Paulo" (C001, C003, C007, C008, C016) mostram "Selecione o Nome" ao serem abertos.
- Uma única mensagem ao salvar, dizendo o que aconteceu no banco e no FlowUp.
- Ícone e tela de abertura passaram para `matriz/` (antes eram lidos da pasta de dados). O `.spec` usa caminhos relativos ao próprio arquivo.
- `requirements.txt` refeito só com o que o programa usa (antes era a lista de outro ambiente, sem o `pendulum`).
- Versão exibida na barra de título.

### Adicionado
- `config.py`: pasta de dados, versão, leitura do `config.json` e log em um só lugar. A variável `CHAMADOS_PASTA_DADOS` permite testar com uma cópia dos dados.
- Log em `Banco de dados\logs`, um arquivo por usuário e mês, com as chamadas ao FlowUp e os erros das telas.
- `ferramentas/diagnostico_flowup.py`: verificação somente leitura da integração e geração de token novo.
- Testes automáticos em `testes/`.
- README, documentação em `docs/`, `.gitignore`, `.gitattributes` e `config.example.json`.

### Removido
Arquivos da versão 1.x que não fazem parte do projeto e devem ser apagados da pasta antes de publicar no GitHub:
- `build\`, `dist\` (recriados a cada compilação), `venv\` (criado em outro computador, apontando para `C:\Users\paulo.victor`; não funciona em outra máquina) e `erros\` (logs vazios de 2025).
- `Ver tarefa.py` (script de teste com o token escrito no código e o endereço antigo da API).
- `Status.csv` (IDs de status, agora no `config.json`).
- `LEIA ANTES DE RECOMPILAR.docx`, `Diagnostico flowup e limpeza.md` e a pasta `Guia relatório de bugs\` (conteúdo útil incorporado em `docs/`; os guias de Dynamo não eram deste projeto e as explicações descreviam a versão antiga).
- `Thumbs.db` em `Banco de dados\` e em `matriz\`.
- Função `_criar_csv_exemplo` em `Bugs.py` (nunca era chamada).

## Histórico anterior

Reconstituído a partir das datas dos arquivos e do banco em outubro de 2026.

- **Outubro de 2025:** primeira versão (formulário com banco SQLite). Guias de uso e os primeiros logs são desse mês.
- **Janeiro de 2026:** integração com o FlowUp. Primeira tarefa criada em 15/01/2026 (C001).
- **Março de 2026:** banco passou a ser lido da pasta `Banco de dados` na rede por caminho fixo; tela de abertura e executável "Abertura de Chamados" (compilação de 20/03/2026).
- **Junho de 2026:** última tarefa criada pelo endereço antigo da API (C031, 03/06/2026).

# Manutenção e solução de problemas

## Primeiro passo: o diagnóstico

Com o ambiente de desenvolvimento pronto ([desenvolvimento-e-distribuicao.md](desenvolvimento-e-distribuicao.md)), na pasta do projeto:

```bat
.venv\Scripts\activate
python ferramentas\diagnostico_flowup.py
```

Ele lê a pasta de dados real e o FlowUp **sem alterar nada** e verifica, nesta ordem:

1. se a pasta de dados e os arquivos `chamados.db`, `nomes_equipe.csv` e `config.json` existem;
2. se o token é aceito e se o quadro e o projeto configurados existem e estão ativos;
3. se cada status do `config.json` existe no quadro;
4. se a lista da equipe bate com os usuários ativos do FlowUp (inativos, IDs que mudaram de dono, pessoas fora da lista);
5. quais chamados têm responsável e ainda não têm tarefa.

Exemplo de saída com tudo certo, exceto dois chamados pendentes:

```
== API do FlowUp
[ OK ] Token aceito. Quadro 2271: CHAMADOS e PROTOCOLOS
[ OK ] Projeto 151: SETOR DE QUALIDADE

== Status do quadro x config.json
[ OK ] Em execução -> 11585 (Em andamento)
...
== Chamados designados sem tarefa no FlowUp
[AVISO] C032 (responsável: Joao Gabriel Rodrigues, status: Não visto). Abra o chamado no programa e salve para criar a tarefa.
```

Outros usos:

```bat
python ferramentas\diagnostico_flowup.py --tarefa 51808    mostra uma tarefa do FlowUp
python ferramentas\diagnostico_flowup.py --gerar-token     gera um token novo
```

## Verificação do computador

Quando o programa não abre direito em uma máquina, use o botão **Verificar computador** no topo (ou veja a janela que abre sozinha quando há erro). Ele confere, em poucos segundos:

| Item | Erro ou aviso significa |
|---|---|
| Pasta da rede | Drive Z: não mapeado, VPN desconectada ou sem acesso à pasta `Banco de dados` (o programa não funciona) |
| Permissão de gravação | Usuário sem permissão de gravação na pasta de dados (o programa não funciona) |
| Banco de chamados | Banco ausente ou travado (por exemplo, aberto no DB Browser) |
| Lista da equipe | `nomes_equipe.csv` ausente ou ilegível |
| Configuração do FlowUp | `config.json` ausente ou sem token |
| Conexão com o FlowUp | A máquina não alcança `https://api.flowup.me` (internet, proxy ou firewall) ou o token foi recusado |

O botão "Copiar relatório" copia o resultado para colar num chamado de Suporte TI. Cada verificação também fica no log da pessoa. O exe já traz o Python e todas as bibliotecas: não é preciso instalar nada no computador.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "A API respondeu com redirecionamento (HTTP 302 ...)" | A FlowUp mudou o endereço da API | Ver [Quando a FlowUp mudar a API](#quando-a-flowup-mudar-a-api) |
| "Token do FlowUp inválido ou expirado (HTTP 401)" | Token vencido, trocado ou revogado | Gerar token novo ([configuracao.md](configuracao.md#token-do-flowup)) |
| "...integração com o FlowUp não está configurada (token ausente...)" | `config.json` ausente, ilegível ou sem token | Conferir o arquivo na pasta de dados; o diagnóstico aponta o problema |
| "Responsável 'X' não está no nomes_equipe.csv" | Pessoa nova ou nome digitado à mão | Incluir a pessoa com o ID do FlowUp ([configuracao.md](configuracao.md#lista-da-equipe-nomes_equipecsv)) |
| "HTTP 400: Tarefa não encontrada" ao salvar | A tarefa foi apagada no FlowUp | Se precisar de tarefa nova, apague o número da tarefa do chamado (ver [Recriar ou vincular tarefa](#recriar-ou-vincular-tarefa)) e salve de novo |
| "A API aceitou o pedido, mas não devolveu o ID da tarefa" | A resposta da API mudou de formato | **Não salve de novo antes de olhar o FlowUp**: a tarefa pode ter sido criada. Vincule o número à mão e ajuste `extrair_task_id` em `flowup_api.py` para o formato novo (a resposta completa está no log) |
| Status não muda no FlowUp, ou erro de status | ID de status do `config.json` não existe no quadro | Rodar o diagnóstico e corrigir o campo `status` |
| Tela "Erro ao carregar" ao abrir o programa | Drive Z: desconectado, sem permissão ou pasta movida | Conferir o mapeamento do Z: e a pasta de dados |
| Lista de nomes mostra "ERRO: Verifique a Rede Z:" ou "Equipe Vazia" | `nomes_equipe.csv` ausente, com colunas erradas ou salvo em outro formato | Conferir o arquivo: colunas `Id,Name,Email`, separador vírgula, UTF-8 |
| "database is locked" no log | Gravação simultânea ou banco aberto no DB Browser com alterações não gravadas | Fechar o DB Browser e tentar de novo |
| Chamado designado e sem tarefa | Falha na criação (rede, token, API) | Abrir o chamado e salvar de novo. Desde a 2.0 isso cria a tarefa |
| Imagem de chamado antigo não aparece | Na 1.x as imagens iam para uma pasta temporária e se perdiam ao fechar o programa | Não há como recuperar. Os anexos da 2.0 ficam em `Banco de dados\anexos` |
| Mudanças feitas no FlowUp não aparecem no programa | A integração só envia, não lê de volta | Comportamento esperado ([arquitetura.md](arquitetura.md#o-que-a-integração-não-faz)) |

## Recriar ou vincular tarefa

O vínculo entre chamado e tarefa é a coluna `flowup_task_id` do banco.

- **Vincular uma tarefa que já existe** (criada à mão ou criada sem o número ter sido gravado):
  `UPDATE chamados SET flowup_task_id = 52000 WHERE protocolo = 'C035';`
- **Criar uma tarefa nova** para um chamado cuja tarefa foi apagada:
  `UPDATE chamados SET flowup_task_id = NULL WHERE protocolo = 'C021';` e depois abrir o chamado no programa e salvar.

Veja abaixo como executar comandos no banco com segurança.

## Logs

Ficam em `Banco de dados\logs`, um arquivo por usuário do Windows e por mês: `2026-10_henrique.viana.log`. Se a rede estiver fora, o programa grava em `%TEMP%\chamados_logs` da máquina da pessoa.

O que procurar:

```
2026-10-17 09:12:01,204 INFO [Bugs] Sistema de Chamados v2.0.0 iniciado por henrique.viana. Pasta de dados: ...
2026-10-17 09:13:40,518 INFO [flowup_api] FlowUp POST https://api.flowup.me/v1/Task/Create -> HTTP 200
2026-10-17 09:13:40,519 INFO [flowup_api] FlowUp resposta: {...}
2026-10-17 09:13:40,526 INFO [janelas] Tarefa 52000 criada para C032
```

Linhas `ERROR` e `CRITICAL` trazem o detalhe técnico do erro. Logs de meses antigos podem ser apagados quando não forem mais úteis.

## Banco de dados

O banco é um arquivo SQLite (`Banco de dados\chamados.db`). Para consultar ou corrigir dados, use o **DB Browser for SQLite** (https://sqlitebrowser.org/dl/, instalador para Windows 64 bits).

Para só consultar, abra com "Open Database Read Only". Para corrigir:

1. Faça um backup do arquivo antes (ver abaixo).
2. De preferência, faça a correção quando ninguém estiver usando o programa.
3. Abra o banco, vá na aba "Execute SQL", rode o comando e clique em **Write Changes**. Sem esse clique nada é gravado, e enquanto houver alteração pendente a equipe não consegue gravar no banco.
4. Feche o DB Browser.

Consultas úteis:

```sql
-- Chamados designados sem tarefa no FlowUp
SELECT protocolo, responsavel, status FROM chamados
WHERE COALESCE(responsavel,'') <> '' AND flowup_task_id IS NULL AND status <> 'Fechado';

-- Quantidade por status
SELECT status, COUNT(*) FROM chamados GROUP BY status;

-- Chamados de uma pessoa
SELECT protocolo, tema, status FROM chamados WHERE responsavel = 'Henrique' ORDER BY id DESC;
```

Nunca apague o `chamados.db` e não substitua o arquivo por uma cópia antiga sem avisar a equipe: tudo o que foi registrado depois da cópia se perde.

## Backup

Não há backup automático feito pelo programa. Recomendação mínima:

- copiar o `chamados.db` antes de cada versão nova e uma vez por mês para `Banco de dados\backup\chamados_AAAA-MM-DD.db`;
- confirmar com a TI se a pasta do Z: entra no backup da rede.

O `nomes_equipe.csv` e o `config.json` mudam pouco, mas entram na mesma cópia.

## Quando a FlowUp mudar a API

Foi o que derrubou a integração em 2026. Sinais: erro de redirecionamento (HTTP 302) ou de endereço (HTTP 404) ao salvar, e o diagnóstico acusando o endereço.

1. Abra https://www.flowup.me e procure o link "API" no rodapé. Em outubro de 2026 ele apontava para https://api.flowup.me/swagger.
2. Compare os endereços da documentação com os usados em `flowup_api.py` (`Task/Create`, `Task/Update`, `Task/GetTask/{id}`).
3. Se mudou só o servidor ou a versão, ajuste `url_base` ou `versao_api` no `config.json` (não precisa recompilar).
4. Se mudou o caminho dos recursos ou o formato dos dados, ajuste `flowup_api.py` e o payload em `janelas.py` (`_montar_payload_flowup`), recompile e distribua.
5. Rode o diagnóstico e salve um chamado pendente para confirmar.

## Histórico de incidentes

### Outubro de 2026: tarefas pararam de ser criadas

- **Sintoma:** desde agosto de 2026, chamados designados não geravam tarefa no FlowUp (C032, de 17/08, e C033, de 21/09). Salvar de novo não resolvia.
- **Causa 1:** a FlowUp desativou o endereço antigo da API (`https://task.flowup.me/api/v1/public/task/...`), que passou a redirecionar para uma página de erro. A API atual fica em `https://api.flowup.me/v1/...`. A última tarefa criada pelo endereço antigo foi a do C031, em 03/06/2026. O token continuou válido no endereço novo.
- **Causa 2:** o programa decidia entre criar e atualizar pelo campo responsável, e gravava o responsável no banco antes de chamar a API. Depois da primeira falha o chamado ficava com responsável e sem tarefa, e o programa não tentava mais criar, sem mostrar nenhum aviso.
- **Problemas encontrados junto:** IDs de status fictícios (12345 a 12348) para Em execução, Solucionado, Não solucionado e Fechado, o que fazia essas atualizações falharem; lista da equipe desatualizada (IDs 31 e 68 reaproveitados pelo FlowUp, três pessoas inativas, cinco pessoas fora da lista); seguidor fixo 31 apontando para outra pessoa; anexos gravados em pasta temporária; nenhum log de erro; token escrito no código.
- **Correção:** versão 2.0.0 (ver [CHANGELOG.md](../CHANGELOG.md)).
- **Pendente na época:** C032 e C033 seriam criados salvando os chamados de novo na versão 2.0.0.

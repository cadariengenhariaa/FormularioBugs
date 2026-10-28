# Configuração

Tudo o que muda de ambiente para ambiente, ou ao longo do tempo, fica fora do código: na pasta de dados da rede (`config.json` e `nomes_equipe.csv`) ou no `config.py`. Alterações no `config.json` e no `nomes_equipe.csv` **não exigem recompilar** o programa.

## Pasta de dados

Definida em `config.py`:

```python
PASTA_DADOS_PADRAO = r"Z:\Biblioteca\Padronização\Cadari\Processos BIM\Formulário de bugs\Banco de dados"
```

Se a pasta mudar de lugar na rede, altere essa linha, recompile e distribua o exe novo. Para testes, a variável de ambiente `CHAMADOS_PASTA_DADOS` substitui o padrão sem mexer no código.

| Variável de ambiente | Uso |
|---|---|
| `CHAMADOS_PASTA_DADOS` | Usa outra pasta de dados (testes, homologação) |
| `CHAMADOS_FLOWUP_TOKEN` | Usa outro token sem editar o `config.json` |

## config.json

Fica na pasta de dados e **não vai para o GitHub**. O modelo está em `config.example.json` na raiz do repositório, com o token vazio (token vazio = integração desligada).

```json
{
  "flowup": {
    "url_base": "https://api.flowup.me",
    "versao_api": "v1",
    "token": "<token gerado conforme a seção Token do FlowUp>",
    "projeto_id": 151,
    "quadro_id": 2271,
    "tag": {"Id": 286, "Name": "Chamados", "Color": "#ff4500", "Active": true},
    "seguidores_fixos": [10],
    "status": {
      "Não visto": 11583,
      "Visto": 11583,
      "Em execução": 11585,
      "Solucionado": 11584,
      "Não solucionado": 11677,
      "Fechado": 11584
    },
    "timeout_segundos": 30
  }
}
```

| Campo | O que é | Valor atual |
|---|---|---|
| `url_base` | Endereço da API pública do FlowUp, sem barra no final | `https://api.flowup.me` |
| `versao_api` | Versão usada nos endereços (`/v1/Task/Create`) | `v1` |
| `token` | Token de acesso à API (ver abaixo) | só no arquivo da rede |
| `projeto_id` | Projeto onde as tarefas são criadas | 151 (SETOR DE QUALIDADE) |
| `quadro_id` | Quadro dentro do projeto | 2271 (CHAMADOS e PROTOCOLOS) |
| `tag` | Etiqueta aplicada a toda tarefa | 286, "Chamados" |
| `seguidores_fixos` | IDs de usuários que seguem todas as tarefas, além do solicitante | `[10]` (Renata) |
| `status` | Conversão do status do programa para o ID do status no quadro | ver tabela em [arquitetura.md](arquitetura.md#status) |
| `timeout_segundos` | Tempo máximo de espera por resposta da API | 30 |

Campos ausentes assumem os valores padrão de `FLOWUP_PADRAO` em `config.py`. No campo `status`, basta escrever os status que mudam; os outros continuam com o padrão.

Quando as mudanças valem: o token e o endereço são lidos a cada chamada à API; os IDs, os seguidores e os status, cada vez que a janela "Acompanhar Chamado" é aberta.

Cuidados ao editar:
- Use o Bloco de Notas ou o VS Code e salve em UTF-8. O arquivo precisa continuar sendo um JSON válido (aspas duplas, vírgula entre os itens, nenhuma vírgula depois do último).
- Depois de editar, rode `python ferramentas\diagnostico_flowup.py`. Ele lê o mesmo arquivo e confere os IDs no FlowUp.

## Token do FlowUp

O programa se autentica com um token Bearer. O token é gerado a partir de uma **senha de API**, que é fornecida pelo suporte da FlowUp (não é a senha de login de uma pessoa).

### Gerar um token novo

Com a senha de API em mãos:

```bat
python ferramentas\diagnostico_flowup.py --gerar-token
```

A ferramenta pede o subdomínio da instância FlowUp da Cadari e a senha, chama o endpoint `/token` e oferece gravar o token no `config.json`. Não é preciso recompilar nem reiniciar os programas abertos.

O mesmo pode ser feito à mão, conforme a documentação da API (https://api.flowup.me/swagger):

```
POST https://api.flowup.me/token
Content-Type: application/x-www-form-urlencoded

password=<senha da API>&grant_type=password&scope=api&subdomain=<subdomínio>
```

A resposta traz `access_token` (o token) e `expires_in` (validade em segundos).

### Quando trocar o token
- O diagnóstico ou o programa acusam HTTP 401 (token recusado ou vencido).
- O token vazou (por exemplo, foi parar no GitHub ou num e-mail). Peça ao suporte da FlowUp uma senha de API nova, gere outro token e substitua no `config.json`.
- A pessoa que tinha a senha de API saiu da empresa.

## Lista da equipe (nomes_equipe.csv)

Fica na pasta de dados. Define quem aparece nas listas de nome e qual é o ID de cada pessoa no FlowUp.

```
Id,Name,Email
10,Renata,renata@...
48,Henrique,...
```

| Coluna | Uso |
|---|---|
| `Id` | ID do usuário no FlowUp. É o que liga o nome escolhido na tela à pessoa que recebe a tarefa |
| `Name` | Nome mostrado nas listas e gravado nos chamados |
| `Email` | Só para referência; o programa não usa |

**Desde a versão 2.1 a lista é atualizada sozinha** a cada abertura do programa (`equipe.py`): entra quem ficou ativo no FlowUp, sai quem foi desativado e, quando o FlowUp reaproveita um ID para outra pessoa, o nome é trocado. O nome de quem já estava na lista é mantido quando o primeiro nome bate (os chamados antigos guardam o nome como texto). Se o FlowUp não responder, vale o arquivo como está. Para desligar, use `"sincronizar_equipe": false` no `config.json` e mantenha o arquivo à mão com as regras abaixo.

Regras:
- A lista deve ter as mesmas pessoas que estão **ativas** no FlowUp. Quem está na lista e não está ativo não deve ser designado; quem está ativo e fora da lista não consegue abrir chamado.
- **O FlowUp reaproveita IDs.** Quando alguém sai, o mesmo ID pode passar para uma pessoa nova (aconteceu com o 31, que era Paulo e virou Lucas Gomes, e com o 68). Por isso, sempre que alguém entrar ou sair, confira a lista com o diagnóstico.
- Evite renomear quem já tem chamados: os chamados guardam o nome como texto e deixam de bater com a lista.
- Pode editar no Excel (salvar como "CSV UTF-8 (delimitado por vírgulas)") ou no Bloco de Notas. O separador é vírgula.
- A lista é lida quando o programa abre. Quem estiver com o programa aberto precisa fechar e abrir de novo.

Para ver as diferenças entre a lista e o FlowUp:

```bat
python ferramentas\diagnostico_flowup.py
```

A seção "Lista da equipe" mostra quem está inativo, quem está fora da lista e os IDs que mudaram de dono.

## Como descobrir IDs no FlowUp

O diagnóstico já mostra os status do quadro configurado e os usuários ativos. Para outros IDs (outro quadro, projeto ou tag), use a página da API em https://api.flowup.me/swagger: escreva `Bearer <token>` no campo `api_key` do topo da página e use os endpoints de consulta (botão "Try it out!" de cada um):

| Para achar | Endpoint |
|---|---|
| Quadros ativos | `POST /v1/Board/GetActiveBoards` |
| Projetos | `POST /v1/Project/GetAll` |
| Status de um quadro | `GET /v1/Status/GetByBoard?boardId=<id>` |
| Usuários ativos | `GET /v1/User/GetActiveUsers` |
| Uma tarefa | `GET /v1/Task/GetTask/<id>` |

## Opções de software e ferramenta

Estão no dicionário `FERRAMENTAS`, no início de `janelas.py` (vale para o formulário e para o filtro). Ao alterar, recompile e distribua.

## Versão do programa

`VERSAO` em `config.py`. Aparece na barra de título e no log de abertura. Aumente a cada versão distribuída:
- correção sem mudança de comportamento: 2.0.0 para 2.0.1;
- recurso novo: 2.0.0 para 2.1.0;
- mudança que exige ação de todos (pasta de dados nova, banco novo): 2.0.0 para 3.0.0.

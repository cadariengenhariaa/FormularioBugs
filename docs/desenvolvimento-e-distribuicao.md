# Desenvolvimento e distribuição

Passo a passo para preparar o computador, testar uma alteração, gerar o executável e entregar a versão nova para a equipe.

## Pré-requisitos

- Windows 10 ou 11.
- Python 3.12 (as versões 1.x e 2.0 foram feitas com o 3.12.10). Na instalação, marque "Add python.exe to PATH".
- Git ou GitHub Desktop.
- Acesso ao drive Z: (para os dados reais e para distribuir o exe).
- Editor: VS Code é suficiente.

## Preparar o ambiente

```bat
git clone <endereço do repositório>
cd <pasta clonada>
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

O ambiente virtual (`.venv`) é de cada computador e não vai para o GitHub. Se der problema, apague a pasta `.venv` e repita os três últimos comandos.

## Rodar sem mexer nos dados reais

O programa usa a pasta de dados do Z: por padrão. Para testar, crie uma cópia e aponte para ela:

1. Crie `C:\temp\chamados_teste`.
2. Copie para lá `chamados.db` e `nomes_equipe.csv` da pasta `Banco de dados` do Z:.
3. Copie também o `config.example.json` do repositório, renomeando para `config.json`, e deixe o token vazio. Assim a integração fica desligada e nenhum teste cria tarefa de verdade no FlowUp. Se precisar testar a integração, use o token real, mas saiba que as tarefas serão criadas no quadro de produção (apague-as depois) ou peça um quadro de testes e troque o `quadro_id`.
4. Rode:

```bat
.venv\Scripts\activate
set CHAMADOS_PASTA_DADOS=C:\temp\chamados_teste
python Bugs.py
```

No PowerShell, troque a linha do `set` por `$env:CHAMADOS_PASTA_DADOS = "C:\temp\chamados_teste"`.

## Testes

```bat
python -m unittest discover -s testes -v
```

Os testes automáticos usam uma pasta temporária e simulam a API: não acessam a rede, o Z: nem o FlowUp. Cobrem a leitura do `config.json`, os endereços e mensagens de erro da API, a leitura do número da tarefa nas respostas e o fluxo básico do banco.

Antes de distribuir, faça também o teste manual com a cópia dos dados:

- [ ] abrir um chamado com imagem;
- [ ] designar esse chamado (com a integração desligada aparece o aviso de token ausente, o que é esperado);
- [ ] ver a lista, filtrar e exportar CSV;
- [ ] fechar o chamado;
- [ ] `python ferramentas\diagnostico_flowup.py` sem erros na pasta real (ele é somente leitura).

## Gerar o executável

1. Aumente `VERSAO` em `config.py` e registre as mudanças no `CHANGELOG.md`.
2. Com o ambiente virtual ativado, na pasta do projeto:

```bat
pyinstaller --clean --noconfirm "Abertura de Chamados.spec"
```

3. O resultado é `dist\Abertura de Chamados.exe` (cerca de 35 MB). As pastas `build\` e `dist\` são temporárias e não vão para o GitHub.

O `.spec` é a receita da compilação: inclui a pasta `matriz` (imagens), o ícone, a tela de abertura e a importação oculta exigida pelo tkcalendar. Use sempre ele, em vez de montar o comando do PyInstaller à mão.

## Distribuir para a equipe

O exe não se atualiza sozinho. Cada pessoa roda uma cópia, então a versão nova precisa chegar a todos:

1. Guarde o exe anterior com a versão no nome (por exemplo `Abertura de Chamados 1.x.exe`) para poder voltar atrás.
2. Copie o exe novo para o local oficial na rede. Hoje é a pasta `dist\` dentro de `Formulário de bugs` no Z:. Depois da migração para o GitHub, a sugestão é manter só a versão oficial na raiz de `Formulário de bugs`, ao lado da pasta `Banco de dados`.
3. Substitua as cópias das áreas de trabalho (ou troque por um atalho para o exe da rede).
4. Confira a versão na barra de título. O log de cada pessoa (`Banco de dados\logs`) registra a versão aberta, o que ajuda a achar quem ainda usa exe antigo.

Para voltar atrás, distribua o exe anterior. O banco é o mesmo para todas as versões 2.x; a 2.0 não alterou a estrutura da tabela.

## Publicar no GitHub

O `.gitignore` já deixa de fora o ambiente virtual, `build`, `dist`, a pasta `Banco de dados`, qualquer `config.json`, bancos, logs e anexos. Antes do primeiro envio:

1. Apague da pasta os arquivos da versão 1.x que ainda existirem (lista no [CHANGELOG.md](../CHANGELOG.md#removido)). O `Ver tarefa.py` tinha o token escrito no código.
2. Confira que nenhum arquivo do repositório tem token: procure por `Bearer` e por `token` no VS Code (Ctrl+Shift+F). Só devem aparecer o código que lê o token e o texto da documentação.
3. Crie o repositório como **privado** na organização da Cadari.

Com GitHub Desktop: File > Add local repository, escolha a pasta, "create a repository", revise a lista de arquivos (não pode aparecer nada de `Banco de dados`) e publique.

Com a linha de comando:

```bat
git init
git add .
git status
git commit -m "Versão 2.0.0"
git branch -M main
git remote add origin <endereço do repositório>
git push -u origin main
```

Confira o `git status` antes do commit: a lista não pode ter `chamados.db`, `config.json`, `nomes_equipe.csv` nem nada dentro de `Banco de dados`.

Se o token chegar a ser enviado ao GitHub por engano, apagar o arquivo depois não basta (ele fica no histórico). Troque o token (ver [configuracao.md](configuracao.md#quando-trocar-o-token)).

## Fluxo sugerido para alterações

1. Crie uma branch para a alteração.
2. Altere, rode os testes e teste com a cópia dos dados.
3. Atualize a documentação se a regra ou a configuração mudou.
4. Junte na `main`, crie uma tag com a versão (`git tag v2.0.1`), compile e distribua.

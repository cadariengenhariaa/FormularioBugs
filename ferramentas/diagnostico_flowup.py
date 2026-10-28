"""
Diagnóstico da integração com o FlowUp (somente leitura).

Use quando a criação de tarefas parar de funcionar ou antes de publicar uma versão nova.
Não cria nem altera nada no FlowUp nem no banco de chamados.

Uso, na pasta do projeto e com o ambiente virtual ativado:
    python ferramentas\\diagnostico_flowup.py                 verifica tudo
    python ferramentas\\diagnostico_flowup.py --tarefa 51808   mostra uma tarefa do FlowUp
    python ferramentas\\diagnostico_flowup.py --gerar-token    gera um token novo (pede a senha da API)

Lê a mesma pasta de dados do programa (variável CHAMADOS_PASTA_DADOS ou o padrão do config.py).
Explicação de cada verificação: docs/manutencao-e-problemas.md
"""

import argparse
import csv
import getpass
import json
import os
import sys
import unicodedata

import requests

# Permite importar o pacote chamados a partir desta pasta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chamados.config import ARQUIVO_BANCO, ARQUIVO_CONFIG, ARQUIVO_EQUIPE, PASTA_DADOS, carregar_config_flowup  # noqa: E402

OK, AVISO, ERRO = "[ OK ]", "[AVISO]", "[ERRO]"
problemas = 0


def mostrar(nivel, texto):
    global problemas
    if nivel != OK:
        problemas += 1
    print(f"{nivel} {texto}")


def primeiro_nome(nome):
    """Primeiro nome sem acento e em minúsculas, para comparar a lista com o FlowUp."""
    partes = str(nome or "").split()
    texto = unicodedata.normalize("NFKD", partes[0] if partes else "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def chamar(cfg, metodo, recurso, **kwargs):
    url = f"{str(cfg['url_base']).rstrip('/')}/{cfg['versao_api']}/{recurso}"
    cabecalhos = {"Accept": "application/json", "Authorization": f"Bearer {cfg['token']}"}
    return requests.request(metodo, url, headers=cabecalhos, timeout=cfg.get("timeout_segundos", 30),
                            allow_redirects=False, **kwargs)


def verificar_arquivos():
    print(f"\n== Pasta de dados: {PASTA_DADOS}")
    if not os.path.isdir(PASTA_DADOS):
        mostrar(ERRO, "Pasta de dados inacessível. Confira o drive Z: ou a variável CHAMADOS_PASTA_DADOS.")
        return False
    for arquivo in (ARQUIVO_BANCO, ARQUIVO_EQUIPE, ARQUIVO_CONFIG):
        if os.path.isfile(arquivo):
            mostrar(OK, os.path.basename(arquivo))
        else:
            mostrar(ERRO, f"{os.path.basename(arquivo)} não encontrado")
    return True


def verificar_api(cfg):
    print("\n== API do FlowUp")
    if not cfg["token"]:
        mostrar(ERRO, "Token vazio no config.json. Use --gerar-token ou veja docs/configuracao.md.")
        return False
    try:
        r = chamar(cfg, "GET", f"Board/GetBoardInfo/{cfg['quadro_id']}")
    except requests.exceptions.RequestException as e:
        mostrar(ERRO, f"Sem conexão com {cfg['url_base']}: {e}")
        return False
    if r.status_code == 401:
        mostrar(ERRO, "Token recusado (HTTP 401): inválido ou expirado. Gere outro com --gerar-token.")
        return False
    if r.is_redirect or r.status_code == 404:
        mostrar(ERRO, f"Endereço da API não responde como esperado (HTTP {r.status_code} "
                      f"{r.headers.get('Location', '')}). Confira em https://api.flowup.me/swagger se o endereço mudou.")
        return False
    if not r.ok:
        mostrar(ERRO, f"HTTP {r.status_code}: {r.text[:300]}")
        return False
    quadro = r.json()
    mostrar(OK, f"Token aceito. Quadro {cfg['quadro_id']}: {quadro.get('Name')}"
                + (" (ARQUIVADO)" if quadro.get("Archived") else ""))
    if quadro.get("Archived"):
        mostrar(ERRO, "O quadro configurado está arquivado; as tarefas não devem ir para ele.")

    r = chamar(cfg, "GET", f"Project/GetProjectInfo/{cfg['projeto_id']}")
    if r.ok:
        projeto = r.json()
        nivel = OK if projeto.get("IsActive", True) else ERRO
        mostrar(nivel, f"Projeto {cfg['projeto_id']}: {projeto.get('ProjectName')}"
                       + ("" if projeto.get("IsActive", True) else " (INATIVO)"))
    else:
        mostrar(ERRO, f"Projeto {cfg['projeto_id']} não encontrado (HTTP {r.status_code})")
    return True


def verificar_status(cfg):
    print("\n== Status do quadro x config.json")
    r = chamar(cfg, "GET", "Status/GetByBoard", params={"boardId": cfg["quadro_id"]})
    if not r.ok:
        mostrar(ERRO, f"Não foi possível listar os status (HTTP {r.status_code})")
        return
    existentes = {s["StatusId"]: s["Name"] for s in r.json()}
    print("   Status do quadro: " + ", ".join(f"{i} {n}" for i, n in existentes.items()))
    for status_programa, status_id in cfg["status"].items():
        if status_id in existentes:
            mostrar(OK, f"{status_programa} -> {status_id} ({existentes[status_id]})")
        else:
            mostrar(ERRO, f"{status_programa} -> {status_id}: esse ID não existe no quadro")


def verificar_equipe(cfg):
    print("\n== Lista da equipe (nomes_equipe.csv) x usuários ativos no FlowUp")
    r = chamar(cfg, "GET", "User/GetActiveUsers")
    if not r.ok:
        mostrar(ERRO, f"Não foi possível listar os usuários (HTTP {r.status_code})")
        return
    dados = r.json()
    lista = dados.get("Result", []) if isinstance(dados, dict) else dados
    ativos = {int(u["Id"]): " ".join(str(u.get("Name", "")).split()) for u in lista}

    try:
        with open(ARQUIVO_EQUIPE, encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f))
    except OSError as e:
        mostrar(ERRO, f"Não foi possível ler o nomes_equipe.csv: {e}")
        return

    problemas_antes = problemas
    ids_csv = set()
    for linha in linhas:
        try:
            uid = int(str(linha.get("Id", "")).strip())
        except ValueError:
            mostrar(ERRO, f"Linha sem Id numérico: {linha}")
            continue
        ids_csv.add(uid)
        nome = (linha.get("Name") or "").strip()
        if uid not in ativos:
            mostrar(ERRO, f"{uid} {nome}: não é usuário ativo no FlowUp (não deve ser designado como responsável)")
        elif primeiro_nome(nome) != primeiro_nome(ativos[uid]):
            mostrar(AVISO, f"{uid} {nome}: no FlowUp esse ID é \"{ativos[uid]}\" (ID reaproveitado?)")
    for uid, nome in sorted(ativos.items()):
        if uid not in ids_csv:
            mostrar(AVISO, f"{uid} {nome}: ativo no FlowUp e fora do nomes_equipe.csv")
    for uid in cfg.get("seguidores_fixos", []):
        if uid not in ativos:
            mostrar(ERRO, f"Seguidor fixo {uid} não é usuário ativo no FlowUp")
        else:
            mostrar(OK, f"Seguidor fixo {uid}: {ativos[uid]}")
    if problemas == problemas_antes:
        mostrar(OK, f"{len(linhas)} pessoas na lista, todas ativas no FlowUp")


def verificar_chamados_sem_tarefa():
    print("\n== Chamados designados sem tarefa no FlowUp")
    try:
        from chamados.database import buscar_chamados_designados_sem_tarefa
        pendentes = buscar_chamados_designados_sem_tarefa()
    except Exception as e:
        mostrar(ERRO, f"Não foi possível ler o banco: {e}")
        return
    if not pendentes:
        mostrar(OK, "Nenhum")
    for c in pendentes:
        mostrar(AVISO, f"{c['protocolo']} (responsável: {c['responsavel']}, status: {c['status']}). "
                       "Abra o chamado no programa e salve para criar a tarefa.")


def mostrar_tarefa(cfg, task_id):
    r = chamar(cfg, "GET", f"Task/GetTask/{task_id}")
    print(f"HTTP {r.status_code}")
    if r.ok:
        t = r.json()
        campos = ("Id", "Title", "ProjectName", "BoardName", "StatusName", "StatusId", "UserName",
                  "StartDate", "EndDate", "CreationDate", "Finished", "Archived")
        for campo in campos:
            print(f"   {campo}: {t.get(campo)}")
        print("   Seguidores: " + ", ".join(f"{u.get('Id')} {u.get('Name')}" for u in t.get("FollowerUsers") or []))
    else:
        print(r.text[:500])


def gerar_token(cfg):
    """Autenticação documentada em https://api.flowup.me/swagger (endpoint /token)."""
    print("A senha da API é fornecida pelo suporte da FlowUp (não é a senha de login de uma pessoa).")
    subdominio = input("Subdomínio da instância FlowUp da Cadari: ").strip()
    senha = getpass.getpass("Senha da API: ")
    url = f"{str(cfg['url_base']).rstrip('/')}/token"
    r = requests.post(url, data={"password": senha, "grant_type": "password", "scope": "api",
                                 "subdomain": subdominio}, timeout=30)
    if not r.ok:
        print(f"Falhou (HTTP {r.status_code}): {r.text[:300]}")
        return
    dados = r.json()
    token = dados.get("access_token")
    print(f"Token gerado. Validade informada pela API: {dados.get('expires_in')} segundos.")
    if input(f"Gravar o token em {ARQUIVO_CONFIG}? (s/n) ").strip().lower() == "s":
        try:
            with open(ARQUIVO_CONFIG, encoding="utf-8-sig") as f:
                conteudo = json.load(f)
        except FileNotFoundError:
            conteudo = {}
        conteudo.setdefault("flowup", {})["token"] = token
        with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=2)
        print("config.json atualizado. Os programas abertos passam a usar o token novo na próxima ação.")
    else:
        print(token)


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico da integração com o FlowUp (somente leitura).")
    parser.add_argument("--tarefa", type=int, help="ID de uma tarefa do FlowUp para consultar")
    parser.add_argument("--gerar-token", action="store_true", help="gera um token novo pelo endpoint /token")
    args = parser.parse_args()

    cfg = carregar_config_flowup()
    if args.gerar_token:
        gerar_token(cfg)
        return
    if args.tarefa:
        mostrar_tarefa(cfg, args.tarefa)
        return

    if verificar_arquivos() and verificar_api(cfg):
        verificar_status(cfg)
        verificar_equipe(cfg)
    verificar_chamados_sem_tarefa()
    print(f"\nResultado: {'nenhum problema encontrado' if not problemas else f'{problemas} ponto(s) para verificar'}")


if __name__ == "__main__":
    main()

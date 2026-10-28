"""
Lista da equipe (nomes_equipe.csv) sincronizada com os usuários ativos do FlowUp.

A cada abertura do programa:
1. busca os usuários ativos no FlowUp;
2. atualiza o nomes_equipe.csv da pasta de dados (entra quem é novo, sai quem foi
   desativado, troca o nome quando o FlowUp reaproveita um ID para outra pessoa);
3. se o FlowUp não responder, usa o CSV como está.

O nome de quem já está na lista é mantido quando o primeiro nome bate com o do FlowUp
(sem acento), porque os chamados antigos guardam o nome como texto.
Detalhes: docs/configuracao.md
"""

import csv
import io
import logging
import os
import unicodedata

from .config import ARQUIVO_EQUIPE

CAMPOS = ["Id", "Name", "Email"]


def primeiro_nome(nome):
    partes = str(nome or "").split()
    texto = unicodedata.normalize("NFKD", partes[0] if partes else "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def ler_csv(arquivo=ARQUIVO_EQUIPE):
    """Lê o CSV e devolve [{"Id": int, "Name": str, "Email": str}, ...]. Linhas inválidas são ignoradas."""
    linhas = []
    with open(arquivo, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            limpo = {str(k).lower().strip(): (v or "").strip() for k, v in row.items() if k}
            nome = limpo.get("name") or limpo.get("nome")
            uid = limpo.get("id", "")
            if nome and uid.isdigit():
                linhas.append({"Id": int(uid), "Name": nome, "Email": limpo.get("email", "")})
    return linhas


def mesclar(atuais, usuarios_flowup):
    """
    Aplica as regras de sincronização. Função pura (sem arquivo nem rede), usada pelos testes.
    Devolve (nova_lista, alteracoes) onde alteracoes é uma lista de textos para o log.
    """
    por_id = {p["Id"]: p for p in atuais}
    nova, alteracoes = [], []
    for u in usuarios_flowup:
        try:
            uid = int(u.get("Id"))
        except (TypeError, ValueError):
            continue
        nome_fu = " ".join(str(u.get("Name") or "").split())
        email_fu = str(u.get("Email") or "").strip()
        if not nome_fu:
            continue
        atual = por_id.get(uid)
        if atual is None:
            nova.append({"Id": uid, "Name": nome_fu, "Email": email_fu})
            alteracoes.append(f"incluído {uid} {nome_fu}")
        elif primeiro_nome(atual["Name"]) != primeiro_nome(nome_fu):
            nova.append({"Id": uid, "Name": nome_fu, "Email": email_fu})
            alteracoes.append(f"ID {uid} passou de {atual['Name']} para {nome_fu}")
        else:
            nova.append({"Id": uid, "Name": atual["Name"], "Email": atual["Email"] or email_fu})
    ids_ativos = {p["Id"] for p in nova}
    for p in atuais:
        if p["Id"] not in ids_ativos:
            alteracoes.append(f"removido {p['Id']} {p['Name']} (inativo no FlowUp)")
    nova.sort(key=lambda p: p["Id"])
    return nova, alteracoes


def gravar_csv(lista, arquivo=ARQUIVO_EQUIPE):
    """Grava de forma segura: escreve num arquivo temporário e só então substitui o original."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CAMPOS, lineterminator="\r\n")
    w.writeheader()
    for p in lista:
        w.writerow({"Id": p["Id"], "Name": p["Name"], "Email": p["Email"]})
    temporario = arquivo + ".tmp"
    with open(temporario, "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())
    os.replace(temporario, arquivo)


def carregar_equipe(sincronizar=True, timeout=None):
    """
    Devolve (mapa_nome_para_id, mensagem). A mensagem descreve o que aconteceu
    (para a tela de carregamento e o log).
    """
    try:
        atuais = ler_csv()
    except FileNotFoundError:
        atuais = []
    except Exception as e:
        logging.error("Não foi possível ler %s: %s", ARQUIVO_EQUIPE, e)
        atuais = []

    mensagem = "Lista da equipe carregada do arquivo."
    if sincronizar:
        from .flowup_api import listar_usuarios_ativos
        ok, usuarios = listar_usuarios_ativos(timeout=timeout)
        if ok and usuarios:
            nova, alteracoes = mesclar(atuais, usuarios)
            if alteracoes:
                try:
                    gravar_csv(nova)
                    logging.info("Equipe sincronizada com o FlowUp: %s", "; ".join(alteracoes))
                except OSError as e:
                    logging.error("Não foi possível gravar %s: %s", ARQUIVO_EQUIPE, e)
            atuais = nova
            mensagem = "Equipe atualizada pelo FlowUp."
        else:
            logging.warning("Equipe não sincronizada com o FlowUp: %s", usuarios)
            mensagem = "FlowUp indisponível; usando a lista salva."

    return {p["Name"]: p["Id"] for p in atuais}, mensagem

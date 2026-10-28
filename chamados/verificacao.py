"""
Verificação do computador: confere se a máquina tem o que o programa precisa.

Roda sozinha na abertura (tela de carregamento) e pelo botão "Verificar computador".
O exe já traz o Python e todas as bibliotecas; o que muda de um computador para outro
é o acesso à rede (Z:), a permissão de gravação na pasta de dados e o acesso à internet
(api.flowup.me). Cada item devolve OK, AVISO (o programa funciona com limitação) ou ERRO
(o programa não funciona).
"""

import logging
import os
import platform
import sqlite3
import sys
import time
from dataclasses import dataclass

from .config import ARQUIVO_BANCO, ARQUIVO_CONFIG, ARQUIVO_EQUIPE, PASTA_DADOS, VERSAO, carregar_config_flowup, usuario_atual

OK, AVISO, ERRO = "OK", "AVISO", "ERRO"
TIMEOUT_REDE = 8  # segundos; na abertura não vale a pena esperar mais que isso pelo FlowUp


@dataclass
class Item:
    nome: str
    situacao: str
    detalhe: str
    dica: str = ""


def _tempo(funcao):
    inicio = time.monotonic()
    try:
        return funcao(), time.monotonic() - inicio
    except Exception as e:  # cada verificação devolve um Item; erro inesperado vira ERRO
        return Item("?", ERRO, str(e)), time.monotonic() - inicio


def sistema():
    bits = "64 bits" if sys.maxsize > 2 ** 32 else "32 bits"
    return Item("Computador", OK, f"{platform.platform()} ({bits}), usuário {usuario_atual()}, programa v{VERSAO}")


def pasta_dados():
    if os.path.isdir(PASTA_DADOS):
        return Item("Pasta da rede", OK, PASTA_DADOS)
    unidade = os.path.splitdrive(PASTA_DADOS)[0]
    if unidade and not os.path.exists(unidade + os.sep):
        return Item("Pasta da rede", ERRO, f"A unidade {unidade} não está conectada neste computador.",
                    "Mapear o drive Z: (ou reconectar a VPN) e abrir o programa de novo.")
    return Item("Pasta da rede", ERRO, f"Pasta não encontrada ou sem acesso: {PASTA_DADOS}",
                "Pedir ao TI acesso à pasta Banco de dados do Formulário de bugs.")


def gravacao():
    teste = os.path.join(PASTA_DADOS, f".teste_{usuario_atual()}.tmp")
    try:
        with open(teste, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(teste)
        return Item("Permissão de gravação", OK, "O usuário consegue gravar na pasta de dados.")
    except OSError as e:
        return Item("Permissão de gravação", ERRO, f"Sem permissão para gravar na pasta de dados ({e}).",
                    "Pedir ao TI permissão de leitura e gravação na pasta Banco de dados.")


def banco():
    if not os.path.isfile(ARQUIVO_BANCO):
        return Item("Banco de chamados", AVISO, "chamados.db não existe; será criado na primeira abertura.")
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO, timeout=5)
        total = conn.execute("SELECT COUNT(*) FROM chamados").fetchone()[0]
        conn.close()
        return Item("Banco de chamados", OK, f"{total} chamados registrados.")
    except sqlite3.Error as e:
        return Item("Banco de chamados", ERRO, f"Não foi possível ler o banco: {e}",
                    "Fechar o banco se estiver aberto no DB Browser e tentar de novo.")


def lista_equipe():
    try:
        from .equipe import ler_csv
        total = len(ler_csv(ARQUIVO_EQUIPE))
    except FileNotFoundError:
        return Item("Lista da equipe", AVISO, "nomes_equipe.csv não encontrado; será criado pelo FlowUp.")
    except Exception as e:
        return Item("Lista da equipe", AVISO, f"Não foi possível ler nomes_equipe.csv: {e}")
    return Item("Lista da equipe", OK if total else AVISO, f"{total} pessoas na lista.")


def configuracao():
    if not os.path.isfile(ARQUIVO_CONFIG):
        return Item("Configuração do FlowUp", AVISO, "config.json não encontrado: tarefas não serão criadas.",
                    "Avisar o responsável pelo sistema.")
    if not carregar_config_flowup().get("token"):
        return Item("Configuração do FlowUp", AVISO, "Token vazio no config.json: tarefas não serão criadas.",
                    "Avisar o responsável pelo sistema.")
    return Item("Configuração do FlowUp", OK, "config.json com token.")


def conexao_flowup(timeout=TIMEOUT_REDE):
    from .flowup_api import testar_conexao
    ok, resposta = testar_conexao(timeout=timeout)
    if ok:
        return Item("Conexão com o FlowUp", OK, "api.flowup.me respondeu e aceitou o token.")
    texto = str(resposta)
    if "401" in texto:
        dica = "Token recusado: avisar o responsável pelo sistema."
    elif "conectar" in texto.lower() or "timed out" in texto.lower():
        dica = ("Este computador não alcança api.flowup.me. Verificar internet, proxy ou firewall "
                "(liberar https://api.flowup.me).")
    else:
        dica = "Avisar o responsável pelo sistema (ver docs/manutencao-e-problemas.md)."
    return Item("Conexão com o FlowUp", AVISO, texto[:300], dica)


VERIFICACOES = [sistema, pasta_dados, gravacao, banco, lista_equipe, configuracao, conexao_flowup]


def verificar_tudo(ao_avancar=None):
    """Roda todas as verificações. ao_avancar(indice, total, nome) é chamado antes de cada uma."""
    itens = []
    for i, funcao in enumerate(VERIFICACOES):
        if ao_avancar:
            ao_avancar(i, len(VERIFICACOES), funcao.__name__)
        item, segundos = _tempo(funcao)
        if item.nome == "?":
            item.nome = funcao.__name__
        itens.append(item)
        logging.info("Verificação %s: %s (%.1f s) %s", item.nome, item.situacao, segundos, item.detalhe)
        if funcao is pasta_dados and item.situacao == ERRO:
            break  # sem a pasta, as demais verificações de arquivo não fazem sentido
    return itens


def relatorio_texto(itens):
    linhas = [f"Verificação do computador - Controle de Chamados v{VERSAO}"]
    for it in itens:
        linhas.append(f"[{it.situacao}] {it.nome}: {it.detalhe}" + (f" -> {it.dica}" if it.dica else ""))
    return "\n".join(linhas)

"""
Configuração central do Sistema de Chamados.

Tudo o que depende do ambiente fica neste módulo ou no arquivo config.json
da pasta de dados: local da rede, token do FlowUp, IDs do FlowUp e log.
Nenhum outro módulo deve ter caminho de rede ou senha escrito no código.

Detalhes de cada campo: docs/configuracao.md
"""

import copy
import getpass
import json
import logging
import os
import sys
import tempfile
from datetime import datetime

VERSAO = "2.3.0"

# ---------------------------------------------------------------------------
# Pasta de dados compartilhada
# ---------------------------------------------------------------------------
# Guarda o banco (chamados.db), a lista da equipe (nomes_equipe.csv), o
# config.json, os anexos e os logs. Fica na rede e NUNCA vai para o GitHub.
# Para testar sem mexer na produção, defina a variável de ambiente
# CHAMADOS_PASTA_DADOS com uma pasta local (ver docs/desenvolvimento-e-distribuicao.md).
PASTA_DADOS_PADRAO = r"Z:\Biblioteca\Padronização\Cadari\Processos BIM\Formulário de bugs\Banco de dados"
PASTA_DADOS = os.environ.get("CHAMADOS_PASTA_DADOS") or PASTA_DADOS_PADRAO

ARQUIVO_BANCO = os.path.join(PASTA_DADOS, "chamados.db")
ARQUIVO_EQUIPE = os.path.join(PASTA_DADOS, "nomes_equipe.csv")
ARQUIVO_CONFIG = os.path.join(PASTA_DADOS, "config.json")
PASTA_ANEXOS = os.path.join(PASTA_DADOS, "anexos")
PASTA_LOGS = os.path.join(PASTA_DADOS, "logs")


def resource_path(relative_path):
    """Local de um recurso empacotado (pasta matriz), no código-fonte ou no exe do PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def resolver_caminho_dados(caminho):
    """Converte um caminho relativo salvo no banco (ex.: anexos/C001_print.png) em caminho absoluto."""
    if not caminho:
        return caminho
    if os.path.isabs(caminho):
        return caminho
    return os.path.join(PASTA_DADOS, caminho)


# ---------------------------------------------------------------------------
# FlowUp
# ---------------------------------------------------------------------------
# Valores padrão. O config.json da pasta de dados pode sobrescrever qualquer
# um deles; o token só existe lá (ou na variável CHAMADOS_FLOWUP_TOKEN).
FLOWUP_PADRAO = {
    "url_base": "https://api.flowup.me",
    "versao_api": "v1",
    "token": "",
    "projeto_id": 151,
    "quadro_id": 2271,
    "tag": {"Id": 286, "Name": "Chamados", "Color": "#ff4500", "Active": True},
    "seguidores_fixos": [10],
    # Status do quadro (os mesmos nomes do FlowUp). Ao abrir, o programa lê a lista atual do
    # quadro no FlowUp; estes valores só valem se o FlowUp não responder.
    "status": {
        "Novas": 11583,
        "Em andamento": 11585,
        "Pendência Interna": 11677,
        "Finalizadas": 11584,
    },
    "status_final": "Finalizadas",
    "timeout_segundos": 30,
}


def carregar_config_flowup():
    """
    Lê a seção "flowup" do config.json e completa com os valores padrão.

    Nunca lança exceção: se o arquivo não existir ou estiver inválido, devolve
    os padrões (sem token) e registra o problema no log. Quem chama decide o
    que fazer quando o token está vazio.
    """
    cfg = copy.deepcopy(FLOWUP_PADRAO)
    try:
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8-sig") as f:
            dados = json.load(f)
        secao = dados.get("flowup", {}) if isinstance(dados, dict) else {}
        for chave, valor in secao.items():
            if chave == "status" and isinstance(valor, dict):
                cfg["status"].update(valor)
            else:
                cfg[chave] = valor
    except FileNotFoundError:
        logging.warning("config.json não encontrado em %s. Integração com o FlowUp desativada.", ARQUIVO_CONFIG)
    except (OSError, ValueError) as e:
        logging.error("Não foi possível ler %s: %s", ARQUIVO_CONFIG, e)

    token_ambiente = os.environ.get("CHAMADOS_FLOWUP_TOKEN")
    if token_ambiente:
        cfg["token"] = token_ambiente
    cfg["token"] = (cfg.get("token") or "").strip()
    return cfg


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------
def usuario_atual():
    try:
        return getpass.getuser()
    except Exception:
        return "desconhecido"


def configurar_log():
    """
    Grava o log em <pasta de dados>/logs/AAAA-MM_<usuario>.log.
    Se a rede não estiver acessível, usa a pasta temporária do Windows.
    Devolve o arquivo de log em uso.
    """
    nome = f"{datetime.now():%Y-%m}_{usuario_atual()}.log"
    arquivo = None
    # Só usa a pasta da rede se ela já existir (o log não deve criar a pasta de dados)
    pastas = [PASTA_LOGS] if os.path.isdir(PASTA_DADOS) else []
    for pasta in pastas + [os.path.join(tempfile.gettempdir(), "chamados_logs")]:
        try:
            os.makedirs(pasta, exist_ok=True)
            arquivo = os.path.join(pasta, nome)
            handler = logging.FileHandler(arquivo, encoding="utf-8", delay=True)
            break
        except OSError:
            arquivo = None
            continue
    handlers = [logging.StreamHandler()]
    if arquivo:
        handlers.insert(0, handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(module)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    return arquivo

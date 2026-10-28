"""
Integração com a API pública do FlowUp.

Documentação oficial: https://api.flowup.me/swagger
Endereços usados: {url_base}/{versao_api}/Task/Create, Task/Update, Task/GetTask/{id},
Task/Delete/{id} e User/GetActiveUsers.
O token e os IDs vêm do config.json da pasta de dados (ver config.py).

Todas as funções devolvem (sucesso, resposta). Em caso de falha, "resposta" é
um texto curto pronto para mostrar ao usuário; o detalhe completo vai para o log.
"""

import logging

import requests

from .config import carregar_config_flowup


class FlowupNaoConfigurado(Exception):
    """O token do FlowUp não está configurado (config.json ausente ou sem token)."""


def _url(cfg, recurso):
    base = str(cfg["url_base"]).rstrip("/")
    return f"{base}/{cfg['versao_api']}/{recurso}"


def _cabecalhos(cfg):
    if not cfg.get("token"):
        raise FlowupNaoConfigurado(
            "Token do FlowUp não configurado. Preencha o campo \"token\" no config.json da pasta de dados."
        )
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {cfg['token']}",
    }


def _explicar_falha(response):
    """Traduz a resposta de erro em uma mensagem curta e útil."""
    codigo = response.status_code
    if 300 <= codigo < 400:
        destino = response.headers.get("Location", "?")
        return (f"A API respondeu com redirecionamento (HTTP {codigo} para {destino}). "
                "Provável mudança de endereço da API do FlowUp. Ver docs/manutencao-e-problemas.md.")
    if codigo == 401:
        return "Token do FlowUp inválido ou expirado (HTTP 401). Gere um novo token (docs/configuracao.md)."
    if codigo == 404:
        return "Endereço da API não encontrado (HTTP 404). Confira url_base e versao_api no config.json."
    corpo = (response.text or "").strip().replace("\r", " ").replace("\n", " ")
    return f"HTTP {codigo}: {corpo[:300]}"


def _enviar(metodo, recurso, payload=None, timeout=None):
    cfg = carregar_config_flowup()
    try:
        cabecalhos = _cabecalhos(cfg)
    except FlowupNaoConfigurado as e:
        logging.warning(str(e))
        return False, str(e)

    url = _url(cfg, recurso)
    try:
        # allow_redirects=False: se a FlowUp mudar o endereço de novo, o erro aparece
        # como redirecionamento em vez de uma página HTML de erro.
        response = requests.request(metodo, url, headers=cabecalhos, json=payload,
                                    timeout=timeout or cfg.get("timeout_segundos", 30), allow_redirects=False)
    except requests.exceptions.RequestException as e:
        logging.error("FlowUp %s %s falhou: %s", metodo, url, e, exc_info=True)
        return False, f"Não foi possível conectar à API do FlowUp: {e}"

    logging.info("FlowUp %s %s -> HTTP %s", metodo, url, response.status_code)
    logging.info("FlowUp resposta: %s", (response.text or "")[:2000])

    if not response.ok or response.is_redirect:
        return False, _explicar_falha(response)
    try:
        return True, response.json()
    except ValueError:
        return True, response.text


def criar_task_flowup(payload):
    """Cria a tarefa no FlowUp. Em caso de sucesso, use extrair_task_id() na resposta."""
    return _enviar("POST", "Task/Create", payload)


def atualizar_task_flowup(payload):
    """Atualiza uma tarefa existente. O payload precisa ter o "Id" da tarefa."""
    return _enviar("PUT", "Task/Update", payload)


def testar_conexao(timeout=8):
    """Consulta leve (informações do quadro) para saber se a API responde e aceita o token."""
    cfg = carregar_config_flowup()
    return _enviar("GET", f"Board/GetBoardInfo/{cfg['quadro_id']}", timeout=timeout)


def obter_task_flowup(task_id):
    """Consulta uma tarefa (somente leitura)."""
    return _enviar("GET", f"Task/GetTask/{int(task_id)}")


def excluir_task_flowup(task_id):
    """Exclui a tarefa no FlowUp (usado ao excluir um chamado)."""
    return _enviar("DELETE", f"Task/Delete/{int(task_id)}")


def listar_status_quadro(quadro_id, timeout=None):
    """Status de um quadro: (True, [{"StatusId":.., "Name":.., "IsFinal":.., "Order":..}]) ou (False, mensagem)."""
    cfg = carregar_config_flowup()
    try:
        cabecalhos = _cabecalhos(cfg)
        r = requests.get(_url(cfg, "Status/GetByBoard"), params={"boardId": quadro_id}, headers=cabecalhos,
                         timeout=timeout or cfg.get("timeout_segundos", 30), allow_redirects=False)
    except (FlowupNaoConfigurado, requests.exceptions.RequestException) as e:
        return False, str(e)
    if not r.ok or r.is_redirect:
        return False, _explicar_falha(r)
    try:
        return True, r.json()
    except ValueError:
        return False, "Resposta inesperada ao listar status do FlowUp."


def listar_usuarios_ativos(timeout=None):
    """Usuários ativos da instância: (True, [{"Id": .., "Name": .., "Email": ..}, ...]) ou (False, mensagem)."""
    ok, resposta = _enviar("GET", "User/GetActiveUsers", timeout=timeout)
    if not ok:
        return False, resposta
    lista = resposta.get("Result", []) if isinstance(resposta, dict) else resposta
    if not isinstance(lista, list):
        return False, "Resposta inesperada ao listar usuários do FlowUp."
    return True, lista


def extrair_task_id(resposta):
    """
    Obtém o ID da tarefa criada a partir da resposta da API.
    Aceita os formatos já vistos ou prováveis: {"taskId": 1}, {"TaskId": 1},
    {"Id": 1}, {"Result": {...}}, 1 ou "1". Devolve None se não encontrar.
    """
    if isinstance(resposta, bool) or resposta is None:
        return None
    if isinstance(resposta, int):
        return resposta if resposta > 0 else None
    if isinstance(resposta, str):
        texto = resposta.strip().strip('"')
        return int(texto) if texto.isdigit() and int(texto) > 0 else None
    if isinstance(resposta, dict):
        for chave in ("taskId", "TaskId", "Id", "id"):
            if chave in resposta:
                valor = extrair_task_id(resposta[chave])
                if valor:
                    return valor
        for chave in ("Result", "result", "Data", "data"):
            if chave in resposta:
                valor = extrair_task_id(resposta[chave])
                if valor:
                    return valor
    return None

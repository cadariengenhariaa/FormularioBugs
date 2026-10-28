"""
Regras de negócio da integração com o FlowUp, separadas das telas (podem ser testadas sem interface).

Regra principal: chamado SEM flowup_task_id -> cria a tarefa; COM flowup_task_id -> atualiza.
O banco é sempre gravado antes; se a API falhar, salvar de novo tenta outra vez.
Detalhes: docs/arquitetura.md
"""

import html
import logging
from datetime import datetime

from .config import carregar_config_flowup
from .database import buscar_chamado_por_protocolo, excluir_chamado_db, salvar_flowup_id_db
from .flowup_api import atualizar_task_flowup, criar_task_flowup, excluir_task_flowup, extrair_task_id


# Status do quadro lidos do FlowUp na abertura do programa: {"Novas": 11583, ...}
STATUS_FLOWUP = {}


def carregar_status(timeout=None):
    """
    Lê os status do quadro configurado no FlowUp (mesma ordem do quadro).
    Devolve (lista_de_nomes, nome_do_status_final). Sem FlowUp, usa o config.json.
    """
    from .flowup_api import listar_status_quadro
    cfg = carregar_config_flowup()
    ok, lista = listar_status_quadro(cfg["quadro_id"], timeout=timeout)
    if ok and lista:
        lista = sorted(lista, key=lambda s: s.get("Order", 0))
        STATUS_FLOWUP.clear()
        STATUS_FLOWUP.update({s["Name"]: s["StatusId"] for s in lista})
        finais = [s["Name"] for s in lista if s.get("IsFinal")]
        return list(STATUS_FLOWUP), (finais[0] if finais else lista[-1]["Name"])
    logging.warning("Status do quadro não lidos do FlowUp (%s); usando o config.json.", lista)
    from .database import STATUS_ANTIGOS
    nomes = [n for n in cfg["status"] if n not in STATUS_ANTIGOS]
    return nomes, cfg.get("status_final", nomes[-1])


class ErroIntegracao(Exception):
    """Falha ao falar com o FlowUp. A mensagem já vem pronta para mostrar ao usuário."""


def descricao_html(chamado):
    """Descrição da tarefa no FlowUp (o editor do FlowUp guarda HTML)."""
    def bloco(texto):
        linhas = [html.escape(linha) for linha in str(texto or "").strip().splitlines()]
        return "<br>".join(linhas)

    partes = [
        f"<p><b>Chamado {html.escape(chamado.get('protocolo') or '')}</b> aberto por "
        f"{html.escape(chamado.get('nome_solicitante') or '')}</p>",
        f"<p><b>Categoria:</b> {html.escape(chamado.get('software') or '')} | "
        f"<b>Assunto:</b> {html.escape(chamado.get('ferramenta') or '')}</p>",
    ]
    if (chamado.get("descricao") or "").strip():
        partes.append(f"<p>{bloco(chamado['descricao'])}</p>")
    if (chamado.get("observacoes") or "").strip():
        partes.append(f"<p><b>Observações da triagem:</b><br>{bloco(chamado['observacoes'])}</p>")
    return "".join(partes)


def montar_payload(chamado, nomes_map, cfg=None):
    """
    Monta o payload de criação/atualização a partir do chamado gravado no banco.
    Lança ErroIntegracao se faltar responsável ou ID.
    """
    cfg = cfg or carregar_config_flowup()
    responsavel = chamado.get("responsavel")
    if not responsavel:
        raise ErroIntegracao("O chamado precisa de um responsável para ir ao FlowUp.")
    user_id = nomes_map.get(responsavel)
    if not user_id:
        raise ErroIntegracao(f"{responsavel} não é usuário ativo no FlowUp (não está na lista da equipe).")

    seguidores = []
    for uid in [nomes_map.get(chamado.get("nome_solicitante"))] + list(cfg.get("seguidores_fixos", [])):
        if uid and uid not in seguidores:
            seguidores.append(uid)

    status_map = {**cfg["status"], **STATUS_FLOWUP}
    status_id = status_map.get(chamado.get("status")) or next(iter(status_map.values()))

    entrega = chamado.get("data_entrega")
    if entrega:
        # Prazo no dia da entrega, das 08:00 às 18:00 (aparece certo no Gantt)
        inicio, fim = f"{entrega}T08:00:00", f"{entrega}T18:00:00"
    else:
        inicio = fim = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Campos fixos herdados da integração original e aceitos pela API desde jan/2026
    return {
        "Id": chamado.get("flowup_task_id") or 0,
        "Title": f"Chamado {chamado.get('protocolo')} - {chamado.get('tema')}",
        "Description": descricao_html(chamado),
        "Comments": [],
        "IsGantt": True,
        "ProjectId": cfg["projeto_id"],
        "BoardId": cfg["quadro_id"],
        "StatusId": status_id,
        "UserId": user_id,
        "StartDate": inicio,
        "EndDate": fim,
        "StartTime": inicio,
        "EndTime": fim,
        "IgnoreHours": True,
        "EstimatedEffort": "string",
        "EstimatedEffortHours": 0,
        "FollowerUsers": seguidores,
        "FollowerTeams": [0],
        "Subtasks": [],
        "Tags": [cfg["tag"]] if cfg.get("tag") else [],
        "ServiceId": 0,
        "CustomFieldAnswers": [],
    }


def sincronizar_tarefa(protocolo, nomes_map):
    """
    Cria ou atualiza a tarefa do chamado (já gravado no banco).
    Devolve a mensagem de sucesso; lança ErroIntegracao em caso de falha.
    """
    cfg = carregar_config_flowup()
    if not cfg.get("token"):
        raise ErroIntegracao("Integração com o FlowUp desativada: token ausente no config.json da pasta de dados.")

    chamado = buscar_chamado_por_protocolo(protocolo)
    if not chamado:
        raise ErroIntegracao(f"Chamado {protocolo} não encontrado no banco.")

    payload = montar_payload(chamado, nomes_map, cfg)
    task_id = chamado.get("flowup_task_id")

    if not task_id:
        logging.info("Criando tarefa no FlowUp para %s", protocolo)
        ok, resposta = criar_task_flowup(payload)
        if not ok:
            raise ErroIntegracao(f"Erro ao criar a tarefa: {resposta}")
        novo_id = extrair_task_id(resposta)
        if not novo_id:
            logging.error("Tarefa do %s sem ID reconhecível na resposta: %r", protocolo, resposta)
            raise ErroIntegracao(
                "A API aceitou o pedido, mas não devolveu o número da tarefa. Confira no FlowUp se a tarefa "
                f"foi criada antes de salvar de novo, para não duplicar.\n\nResposta: {str(resposta)[:300]}"
            )
        salvar_flowup_id_db(protocolo, novo_id)
        logging.info("Tarefa %s criada para %s", novo_id, protocolo)
        return f"Tarefa {novo_id} criada no FlowUp."

    logging.info("Atualizando tarefa %s no FlowUp (%s)", task_id, protocolo)
    ok, resposta = atualizar_task_flowup(payload)
    if not ok:
        raise ErroIntegracao(f"Erro ao atualizar a tarefa {task_id}: {resposta}")
    return f"Tarefa {task_id} atualizada no FlowUp."


def excluir_chamado(protocolo, excluir_tarefa=True):
    """
    Exclui o chamado do banco e, se pedido, a tarefa no FlowUp e o anexo.
    Devolve uma mensagem; lança ErroIntegracao se o chamado não puder ser apagado.
    """
    import os
    from .config import resolver_caminho_dados

    chamado = buscar_chamado_por_protocolo(protocolo)
    if not chamado:
        raise ErroIntegracao(f"Chamado {protocolo} não encontrado.")

    aviso = ""
    task_id = chamado.get("flowup_task_id")
    if excluir_tarefa and task_id and carregar_config_flowup().get("token"):
        ok, resposta = excluir_task_flowup(task_id)
        if ok:
            aviso = f" A tarefa {task_id} foi excluída do FlowUp."
        elif "não encontrada" in str(resposta).lower():
            aviso = f" A tarefa {task_id} já não existia no FlowUp."
        else:
            raise ErroIntegracao(f"O chamado não foi excluído porque a tarefa {task_id} não pôde ser apagada "
                                 f"no FlowUp: {resposta}")

    if not excluir_chamado_db(protocolo):
        raise ErroIntegracao(f"Não foi possível apagar o chamado {protocolo} do banco.")

    anexo = resolver_caminho_dados(chamado.get("caminho_imagem"))
    if anexo and os.path.isfile(anexo):
        try:
            os.remove(anexo)
        except OSError as e:
            logging.warning("Anexo %s não foi apagado: %s", anexo, e)

    logging.info("Chamado %s excluído (tarefa %s)", protocolo, task_id)
    return f"Chamado {protocolo} excluído.{aviso}"

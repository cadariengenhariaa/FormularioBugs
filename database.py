"""
Acesso ao banco SQLite dos chamados.

O arquivo chamados.db fica na pasta de dados compartilhada (config.PASTA_DADOS),
usada ao mesmo tempo por todos que abrem o programa. Estrutura da tabela e
cuidados de manutenção: docs/arquitetura.md e docs/manutencao-e-problemas.md.
"""

import logging
import os
import sqlite3

import pendulum

from config import ARQUIVO_BANCO, PASTA_DADOS

# Mantido por compatibilidade com scripts antigos que importavam DB_FILE.
DB_FILE = ARQUIVO_BANCO

STATUS_INICIAL = "Novas"
# Status usados até a versão 2.1 -> status do quadro do FlowUp
STATUS_ANTIGOS = {
    "Não visto": "Novas",
    "Visto": "Novas",
    "Em execução": "Em andamento",
    "Solucionado": "Finalizadas",
    "Não solucionado": "Pendência Interna",
    "Fechado": "Finalizadas",
}


def converter_para_brasil(data_str):
    """Converte a data gravada pelo SQLite (UTC) para o horário de São Paulo."""
    if not data_str:
        return ""
    try:
        data = pendulum.parse(str(data_str))
        # Sem fuso definido, assume UTC (padrão do CURRENT_TIMESTAMP do SQLite)
        if data.timezone_name == '+00:00' or data.timezone is None:
            data = pendulum.instance(data).in_timezone('UTC')
        return data.in_timezone('America/Sao_Paulo').format('YYYY-MM-DD HH:mm:ss')
    except Exception:
        return data_str


def criar_tabela():
    """Cria a pasta de dados e a tabela de chamados, se ainda não existirem."""
    os.makedirs(PASTA_DADOS, exist_ok=True)
    logging.info("Banco de dados em uso: %s", ARQUIVO_BANCO)

    conn = sqlite3.connect(ARQUIVO_BANCO)
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT UNIQUE,
            nome_solicitante TEXT NOT NULL,
            software TEXT NOT NULL,
            ferramenta TEXT NOT NULL,
            tema TEXT NOT NULL,
            descricao TEXT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Não visto',
            designado_por TEXT,
            responsavel TEXT,
            data_entrega DATE,
            observacoes TEXT,
            ultima_alteracao_por TEXT,
            caminho_imagem TEXT,
            flowup_task_id INTEGER
        )
        """)

        # Bancos criados antes da integração com o FlowUp não têm esta coluna
        try:
            cursor.execute("SELECT flowup_task_id FROM chamados LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE chamados ADD COLUMN flowup_task_id INTEGER")

        # Desde a 2.2 os status são os mesmos do quadro do FlowUp. Converte os nomes antigos.
        for antigo, novo in STATUS_ANTIGOS.items():
            cursor.execute("UPDATE chamados SET status = ? WHERE status = ?", (novo, antigo))
            if cursor.rowcount:
                logging.info("Status convertido: %s -> %s (%s chamados)", antigo, novo, cursor.rowcount)

        conn.commit()
    finally:
        conn.close()


def registrar_chamado_db(nome, software, ferramenta, tema, descricao, caminho_imagem=None):
    """Insere um novo chamado e devolve o protocolo gerado (C001, C002...) ou None."""
    conn = None
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chamados (nome_solicitante, software, ferramenta, tema, descricao, caminho_imagem, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nome, software, ferramenta, tema, descricao, caminho_imagem, STATUS_INICIAL)
        )
        novo_id = cursor.lastrowid
        novo_protocolo = f"C{novo_id:03d}"
        cursor.execute("UPDATE chamados SET protocolo = ? WHERE id = ?", (novo_protocolo, novo_id))
        conn.commit()
        return novo_protocolo
    except Exception as e:
        logging.error(f"Erro ao registrar: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def buscar_chamado_por_protocolo(protocolo):
    """Busca um chamado e converte a data de abertura para o horário de Brasília."""
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chamados WHERE protocolo = ?", (protocolo,))
        chamado = cursor.fetchone()
        conn.close()

        if chamado:
            chamado_dict = dict(chamado)
            chamado_dict['data_hora'] = converter_para_brasil(chamado['data_hora'])
            return chamado_dict
        return None
    except Exception as e:
        logging.error(f"Erro ao buscar: {e}", exc_info=True)
        return None


def atualizar_chamado_db(protocolo, designado_por, responsavel, data_entrega, status, observacoes, usuario_logado, caminho_imagem_atual=None):
    """Atualiza a triagem do chamado. caminho_imagem_atual=None mantém a imagem gravada."""
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()

        query = """
        UPDATE chamados
        SET designado_por = ?, responsavel = ?, data_entrega = ?, status = ?, observacoes = ?, ultima_alteracao_por = ?
        """

        # Garante o formato AAAA-MM-DD
        if data_entrega:
            data_entrega = pendulum.parse(str(data_entrega)).format('YYYY-MM-DD')

        params = [designado_por, responsavel, data_entrega, status, observacoes, usuario_logado]

        if caminho_imagem_atual is not None:
            query += ", caminho_imagem = ?"
            params.append(caminho_imagem_atual)

        query += " WHERE protocolo = ?"
        params.append(protocolo)

        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Erro ao atualizar: {e}", exc_info=True)
        return False


def fechar_chamado_db(protocolo, usuario_logado):
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()
        cursor.execute("UPDATE chamados SET status = 'Fechado', ultima_alteracao_por = ? WHERE protocolo = ?", (usuario_logado, protocolo))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Erro ao fechar: {e}", exc_info=True)
        return False


def atualizar_caminho_imagem_db(protocolo, caminho_imagem):
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()
        cursor.execute("UPDATE chamados SET caminho_imagem = ? WHERE protocolo = ?", (caminho_imagem, protocolo))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro imagem DB: {e}", exc_info=True)


def salvar_flowup_id_db(protocolo, task_id):
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()
        cursor.execute("UPDATE chamados SET flowup_task_id = ? WHERE protocolo = ?", (task_id, protocolo))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ID Flowup: {e}", exc_info=True)


def excluir_chamado_db(protocolo):
    """Apaga o chamado do banco. Devolve True se uma linha foi apagada."""
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chamados WHERE protocolo = ?", (protocolo,))
        apagados = cursor.rowcount
        conn.commit()
        conn.close()
        return apagados > 0
    except Exception as e:
        logging.error(f"Erro ao excluir {protocolo}: {e}", exc_info=True)
        return False


def buscar_chamados_designados_sem_tarefa():
    """Chamados com responsável e sem tarefa no FlowUp (usado pela ferramenta de diagnóstico)."""
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT protocolo, nome_solicitante, responsavel, status, data_hora
            FROM chamados
            WHERE COALESCE(responsavel, '') <> '' AND flowup_task_id IS NULL AND COALESCE(status, '') NOT IN ('Fechado', 'Finalizadas')
            ORDER BY id
        """)
        linhas = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return linhas
    except Exception as e:
        logging.error(f"Erro ao buscar chamados sem tarefa: {e}", exc_info=True)
        return []


def buscar_todos_os_chamados(filtro_status=None, filtro_software=None, filtro_solicitante=None, filtro_responsavel=None):
    try:
        conn = sqlite3.connect(ARQUIVO_BANCO)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM chamados"
        params = []
        conditions = []

        if filtro_status and filtro_status != "Todos":
            conditions.append("status = ?")
            params.append(filtro_status)

        if filtro_software and filtro_software != "Todos":
            conditions.append("software = ?")
            params.append(filtro_software)

        if filtro_solicitante:
            conditions.append("nome_solicitante LIKE ?")
            params.append(f"%{filtro_solicitante}%")

        if filtro_responsavel:
            conditions.append("responsavel LIKE ?")
            params.append(f"%{filtro_responsavel}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC"

        cursor.execute(query, params)
        chamados = cursor.fetchall()
        conn.close()

        chamados_formatados = []
        for chamado in chamados:
            chamado_dict = dict(chamado)
            chamado_dict['data_hora'] = converter_para_brasil(chamado_dict['data_hora'])
            chamados_formatados.append(chamado_dict)

        return chamados_formatados
    except Exception as e:
        logging.error(f"Erro buscar todos: {e}", exc_info=True)
        return []

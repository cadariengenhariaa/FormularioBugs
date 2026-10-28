"""
Testes automáticos básicos. Não acessam a rede, o drive Z: nem o FlowUp.

Rodar na pasta do projeto, com o ambiente virtual ativado:
    python -m unittest discover -s testes -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

# Pasta de dados temporária ANTES de importar o programa (config lê a variável na importação)
PASTA_TESTE = tempfile.mkdtemp(prefix="chamados_teste_")
os.environ["CHAMADOS_PASTA_DADOS"] = PASTA_TESTE
os.environ.pop("CHAMADOS_FLOWUP_TOKEN", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chamados import config, database, flowup_api  # noqa: E402


def resposta_falsa(status, corpo="", location=None):
    r = mock.Mock()
    r.status_code = status
    r.ok = status < 400
    r.is_redirect = 300 <= status < 400 and location is not None
    r.headers = {"Location": location} if location else {}
    r.text = corpo if isinstance(corpo, str) else json.dumps(corpo)
    r.json = (lambda: corpo) if not isinstance(corpo, str) else mock.Mock(side_effect=ValueError)
    return r


def gravar_config(token="token-de-teste", **extra):
    dados = {"flowup": {"token": token, **extra}}
    with open(config.ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)


class TestConfig(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(config.ARQUIVO_CONFIG):
            os.remove(config.ARQUIVO_CONFIG)

    def test_pasta_de_dados_vem_da_variavel_de_ambiente(self):
        self.assertEqual(config.PASTA_DADOS, PASTA_TESTE)

    def test_sem_config_json_usa_padroes_sem_token(self):
        cfg = config.carregar_config_flowup()
        self.assertEqual(cfg["token"], "")
        self.assertEqual(cfg["quadro_id"], 2271)

    def test_config_json_sobrescreve_e_completa_status(self):
        gravar_config(quadro_id=999, status={"Visto": 1})
        cfg = config.carregar_config_flowup()
        self.assertEqual(cfg["token"], "token-de-teste")
        self.assertEqual(cfg["quadro_id"], 999)
        self.assertEqual(cfg["status"]["Visto"], 1)
        self.assertEqual(cfg["status"]["Em andamento"], 11585)  # veio do padrão

    def test_variavel_de_ambiente_tem_prioridade_no_token(self):
        gravar_config(token="do-arquivo")
        with mock.patch.dict(os.environ, {"CHAMADOS_FLOWUP_TOKEN": "da-variavel"}):
            self.assertEqual(config.carregar_config_flowup()["token"], "da-variavel")

    def test_status_padrao_existem_no_quadro_documentado(self):
        ids_do_quadro = {11583, 11585, 11677, 11584}
        self.assertTrue(set(config.FLOWUP_PADRAO["status"].values()) <= ids_do_quadro)


class TestFlowupApi(unittest.TestCase):
    def setUp(self):
        gravar_config()

    def tearDown(self):
        os.remove(config.ARQUIVO_CONFIG)

    def test_cria_tarefa_no_endereco_novo(self):
        with mock.patch.object(flowup_api.requests, "request", return_value=resposta_falsa(200, {"taskId": 123})) as req:
            ok, resposta = flowup_api.criar_task_flowup({"Title": "x"})
        self.assertTrue(ok)
        self.assertEqual(flowup_api.extrair_task_id(resposta), 123)
        metodo, url = req.call_args[0]
        self.assertEqual((metodo, url), ("POST", "https://api.flowup.me/v1/Task/Create"))
        self.assertFalse(req.call_args[1]["allow_redirects"])
        self.assertEqual(req.call_args[1]["headers"]["Authorization"], "Bearer token-de-teste")

    def test_redirecionamento_vira_mensagem_clara(self):
        falsa = resposta_falsa(302, "<html>", location="/Error/NotFound")
        with mock.patch.object(flowup_api.requests, "request", return_value=falsa):
            ok, msg = flowup_api.criar_task_flowup({})
        self.assertFalse(ok)
        self.assertIn("redirecionamento", msg)

    def test_token_recusado(self):
        with mock.patch.object(flowup_api.requests, "request", return_value=resposta_falsa(401, "Acesso negado.")):
            ok, msg = flowup_api.atualizar_task_flowup({"Id": 1})
        self.assertFalse(ok)
        self.assertIn("401", msg)

    def test_sem_token_nao_chama_a_api(self):
        gravar_config(token="")
        with mock.patch.object(flowup_api.requests, "request") as req:
            ok, msg = flowup_api.criar_task_flowup({})
        self.assertFalse(ok)
        req.assert_not_called()

    def test_extrair_task_id_formatos(self):
        casos = [({"taskId": 5}, 5), ({"TaskId": 6}, 6), ({"Id": 7}, 7), ({"Result": {"Id": 8}}, 8),
                 ("9", 9), (10, 10), ("<html>", None), ({"Id": 0}, None), (True, None), (None, None)]
        for entrada, esperado in casos:
            self.assertEqual(flowup_api.extrair_task_id(entrada), esperado, entrada)


class TestBanco(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.criar_tabela()

    def test_fluxo_basico_e_chamado_sem_tarefa(self):
        protocolo = database.registrar_chamado_db("Fulano", "Revit", "Famílias", "Teste", "desc", os.path.join("anexos", "x.png"))
        self.assertRegex(protocolo, r"^C\d{3,}$")

        # Designado e sem tarefa: aparece na lista de pendências
        self.assertTrue(database.atualizar_chamado_db(protocolo, "A", "B", "2026-10-20", "Visto", "obs", "teste"))
        pendentes = [c["protocolo"] for c in database.buscar_chamados_designados_sem_tarefa()]
        self.assertIn(protocolo, pendentes)

        # Salvar sem caminho de imagem mantém o anexo gravado
        chamado = database.buscar_chamado_por_protocolo(protocolo)
        self.assertEqual(chamado["caminho_imagem"], os.path.join("anexos", "x.png"))
        self.assertEqual(chamado["data_entrega"], "2026-10-20")

        database.salvar_flowup_id_db(protocolo, 4242)
        pendentes = [c["protocolo"] for c in database.buscar_chamados_designados_sem_tarefa()]
        self.assertNotIn(protocolo, pendentes)

    def test_caminho_relativo_de_anexo_aponta_para_a_pasta_de_dados(self):
        caminho = config.resolver_caminho_dados(os.path.join("anexos", "C001_print.png"))
        self.assertEqual(caminho, os.path.join(PASTA_TESTE, "anexos", "C001_print.png"))


class TestEquipe(unittest.TestCase):
    def test_mescla_com_flowup(self):
        from chamados import equipe
        atuais = [{"Id": 31, "Name": "Paulo", "Email": ""}, {"Id": 65, "Name": "Joao Gabriel Rodrigues", "Email": ""},
                  {"Id": 42, "Name": "Paloma", "Email": ""}]
        flowup = [{"Id": 31, "Name": "Lucas Gomes"}, {"Id": 65, "Name": "João Gabriel"}, {"Id": 80, "Name": "Nova  Pessoa"}]
        nova, alteracoes = equipe.mesclar(atuais, flowup)
        nomes = {p["Id"]: p["Name"] for p in nova}
        self.assertEqual(nomes, {31: "Lucas Gomes", 65: "Joao Gabriel Rodrigues", 80: "Nova Pessoa"})
        self.assertEqual(len(alteracoes), 3)  # 31 trocado, 80 incluído, 42 removido

    def test_grava_e_le_csv(self):
        from chamados import equipe
        arquivo = os.path.join(PASTA_TESTE, "equipe_teste.csv")
        equipe.gravar_csv([{"Id": 3, "Name": "Simone", "Email": "s@x"}], arquivo)
        self.assertEqual(equipe.ler_csv(arquivo), [{"Id": 3, "Name": "Simone", "Email": "s@x"}])


class TestServico(unittest.TestCase):
    def test_payload_leva_descricao_html(self):
        from chamados import servico
        chamado = {"protocolo": "C100", "tema": "T", "nome_solicitante": "Ana", "responsavel": "Beto",
                   "software": "Revit", "ferramenta": "Famílias", "descricao": "linha 1\n<b>x</b>",
                   "observacoes": "urgente", "status": "Em andamento", "data_entrega": "2026-10-20"}
        p = servico.montar_payload(chamado, {"Ana": 1, "Beto": 2}, config.carregar_config_flowup())
        self.assertIn("linha 1<br>&lt;b&gt;x&lt;/b&gt;", p["Description"])
        self.assertIn("urgente", p["Description"])
        self.assertEqual((p["UserId"], p["StatusId"], p["FollowerUsers"]), (2, 11585, [1, 10]))
        self.assertEqual(p["StartDate"], "2026-10-20T08:00:00")

    def test_responsavel_fora_da_lista(self):
        from chamados import servico
        with self.assertRaises(servico.ErroIntegracao):
            servico.montar_payload({"responsavel": "Fulano"}, {}, config.carregar_config_flowup())


if __name__ == "__main__":
    unittest.main()

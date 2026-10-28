"""
Janela principal do Controle de Chamados.

Abre a tela de carregamento, verifica o computador e lê os dados em segundo plano,
depois monta o topo (abas, tema, zoom) e as duas abas:
- Novo chamado (novo_chamado.py);
- Chamados (lista_chamados.py).

Os status são os mesmos do quadro do FlowUp, lidos na abertura.
"""

import logging
import os
import threading
import time
import traceback
from datetime import datetime
from tkinter import messagebox

import customtkinter

from .. import verificacao
from ..config import FLOWUP_PADRAO, VERSAO, carregar_config_flowup, resource_path, usuario_atual
from ..database import criar_tabela
from ..equipe import carregar_equipe
from ..servico import carregar_status
from . import tema
from .carregamento import TelaCarregamento
from .comum import CALENDARIOS, chave_ordenacao
from .janela_verificacao import JanelaVerificacao
from .lista_chamados import TelaChamados
from .novo_chamado import TelaNovoChamado


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        try:
            import pyi_splash  # tela do PyInstaller enquanto o exe descompacta
            pyi_splash.close()
        except Exception:
            pass

        pref = tema.ler_preferencias()
        customtkinter.set_appearance_mode("Dark" if pref.get("tema") == "escuro" else "Light")
        try:
            tema.escala = min(tema.ZOOM_MAX, max(tema.ZOOM_MIN, float(pref.get("zoom", 1.0))))
        except (TypeError, ValueError):
            tema.escala = 1.0
        customtkinter.set_widget_scaling(tema.escala)
        self.title(f"Controle de Chamados (v{VERSAO})")
        largura, altura = 1320, 840
        self.geometry(f"{largura}x{altura}+{max(0, (self.winfo_screenwidth() - largura) // 2)}"
                      f"+{max(0, (self.winfo_screenheight() - altura) // 2 - 20)}")
        self.minsize(1180, 720)
        self.configure(fg_color=tema.COR["fundo"])
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "icone.ico")))
        except Exception:
            pass

        self.nomes_map = {}
        self.nomes = []
        self.status_nomes, self.status_final = [], ""
        self.verificacao = []
        self._etapa_inicio = time.monotonic()
        self.withdraw()
        self.carregamento = TelaCarregamento(self)
        self._etapa = (0.02, "Iniciando")
        self._resultado = None
        threading.Thread(target=self._carregar, daemon=True).start()
        self.after(60, self._acompanhar)

    # --- carga inicial ---
    def _carregar(self):
        """Verifica o computador e carrega os dados. Roda em segundo plano; nada aqui pode travar a tela."""
        nomes_map = {}
        try:
            etapas = {"sistema": "Verificando o computador", "pasta_dados": "Conectando à pasta da rede",
                      "gravacao": "Conferindo permissão de gravação", "banco": "Abrindo o banco de chamados",
                      "lista_equipe": "Lendo a lista da equipe", "configuracao": "Lendo a configuração",
                      "conexao_flowup": "Testando a conexão com o FlowUp"}

            def avancar(i, total, nome):
                self._etapa = (0.05 + 0.55 * i / total, etapas.get(nome, "Verificando"))
                self._etapa_inicio = time.monotonic()

            self.verificacao = verificacao.verificar_tudo(avancar)
            situacao = {it.nome: it.situacao for it in self.verificacao}
            if situacao.get("Pasta da rede") == verificacao.ERRO:
                raise RuntimeError("pasta da rede inacessível")

            self._etapa, self._etapa_inicio = (0.65, "Preparando o banco de chamados"), time.monotonic()
            criar_tabela()
            flowup_ok = situacao.get("Conexão com o FlowUp") == verificacao.OK
            self._etapa, self._etapa_inicio = (0.8, "Atualizando a equipe pelo FlowUp" if flowup_ok
                                               else "Carregando a lista da equipe"), time.monotonic()
            sincronizar = flowup_ok and bool(carregar_config_flowup().get("sincronizar_equipe", True))
            nomes_map, msg = carregar_equipe(sincronizar=sincronizar, timeout=verificacao.TIMEOUT_REDE)
            if flowup_ok:
                self._etapa, self._etapa_inicio = (0.92, "Lendo os status do quadro no FlowUp"), time.monotonic()
                self.status_nomes, self.status_final = carregar_status(timeout=verificacao.TIMEOUT_REDE)
            self._etapa = (0.97, msg)
            self._resultado = ("ok", nomes_map)
        except Exception as e:
            logging.error("Falha ao carregar os dados: %s", e, exc_info=True)
            self._resultado = ("erro", e)
        if not self.status_nomes:
            self.status_nomes = list(FLOWUP_PADRAO["status"])
            self.status_final = FLOWUP_PADRAO["status_final"]

    def _acompanhar(self):
        fracao, texto = self._etapa
        atual = self.carregamento.valor
        self.carregamento.mostrar(atual + max(0.01, (fracao - atual) * 0.25) if atual < fracao else atual, texto)
        parado = time.monotonic() - self._etapa_inicio
        if not self._resultado and parado > 15:
            self.carregamento.demora.configure(
                text=f"Esta etapa está demorando ({round(parado)} s). Normalmente é a rede: confira o drive Z: e a "
                     "internet. Se não avançar, feche o programa e abra um chamado de Suporte TI.")
        if self._resultado and self.carregamento.valor >= fracao - 0.01:
            self.carregamento.mostrar(1.0, "Pronto")
            self.after(250, self._abrir)
            return
        self.after(40, self._acompanhar)

    def _abrir(self):
        situacao, valor = self._resultado
        self.carregamento.destroy()
        if situacao == "ok":
            self.nomes_map = valor
        self.nomes = sorted(self.nomes_map, key=chave_ordenacao)
        self._montar()
        self.deiconify()
        erros = [i for i in self.verificacao if i.situacao == verificacao.ERRO]
        avisos = [i for i in self.verificacao if i.situacao == verificacao.AVISO]
        if situacao == "erro" or erros:
            JanelaVerificacao(self, self.verificacao or [verificacao.Item("Abertura", verificacao.ERRO, str(valor))])
        elif avisos:
            self.avisar(f"Verificação do computador: {len(avisos)} aviso(s) ({', '.join(a.nome for a in avisos)}). "
                        "Clique em Verificar computador para ver.")

    # --- interface ---
    def _montar(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        topo = customtkinter.CTkFrame(self, fg_color=tema.COR["topo"], corner_radius=0, height=72)
        topo.grid(row=0, column=0, sticky="ew")
        topo.pack_propagate(False)
        customtkinter.CTkLabel(topo, text="", image=tema.imagem("marca_negativa.png", 40)).pack(side="left",
                                                                                               padx=(32, 28))
        customtkinter.CTkFrame(topo, width=1, fg_color=tema.COR["topo_ativo"]).pack(side="left", fill="y", pady=16)
        customtkinter.CTkLabel(topo, text="CONTROLE DE CHAMADOS", text_color=tema.BRANCO,
                               font=tema.fonte(15, "bold")).pack(side="left", padx=24)

        self.abas = {}
        for nome in ("Novo chamado", "Chamados"):
            b = customtkinter.CTkButton(topo, text=nome, width=130, height=72, corner_radius=0,
                                        fg_color="transparent", hover_color=tema.COR["topo_ativo"], text_color=tema.CINZA,
                                        font=tema.fonte(12, "bold"), command=lambda n=nome: self.mostrar_tela(n))
            b.pack(side="left")
            self.abas[nome] = b

        self.tema_escuro = customtkinter.CTkSwitch(topo, text="Tema escuro", text_color=tema.CINZA,
                                                   font=tema.fonte(10), progress_color=tema.DOURADO,
                                                   button_color=tema.CINZA, command=self._trocar_tema)
        self.tema_escuro.pack(side="right", padx=32)
        if tema.escuro():
            self.tema_escuro.select()
        customtkinter.CTkButton(topo, text="Verificar computador", width=150, height=30, corner_radius=4,
                                fg_color="transparent", hover_color=tema.COR["topo_ativo"], border_width=1,
                                border_color="#8FA9B3", text_color=tema.CINZA, font=tema.fonte(10, "bold"),
                                command=self.verificar_computador).pack(side="right", padx=(8, 0))
        self.rotulo_zoom = customtkinter.CTkLabel(topo, text="", text_color="#8FA9B3", font=tema.fonte(10))
        self.rotulo_zoom.pack(side="right", padx=8)
        if tema.escala != 1.0:
            self.rotulo_zoom.configure(text=f"Zoom {round(tema.escala * 100)}%")
        customtkinter.CTkLabel(topo, text=usuario_atual(), text_color="#8FA9B3",
                               font=tema.fonte(10)).pack(side="right", padx=8)

        self.marcador = customtkinter.CTkFrame(self, height=3, fg_color=tema.DOURADO, corner_radius=0)
        self.marcador.grid(row=1, column=0, sticky="ew")

        corpo = customtkinter.CTkFrame(self, fg_color=tema.COR["fundo"], corner_radius=0)
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        tema.estilizar_ttk(self)
        self.tela_novo = TelaNovoChamado(corpo, self)
        self.tela_chamados = TelaChamados(corpo, self)
        for t in (self.tela_novo, self.tela_chamados):
            t.atualizar_nomes(self.nomes)

        barra = customtkinter.CTkFrame(self, fg_color=tema.COR["painel"], corner_radius=0, height=28)
        barra.grid(row=3, column=0, sticky="ew")
        self.aviso = tema.rotulo(barra, "", 9)
        self.aviso.pack(side="left", padx=32, pady=4)
        self.rodape = tema.Rodape(self)
        self.rodape.grid(row=4, column=0, sticky="ew")

        # Zoom: Ctrl + rolagem do mouse, Ctrl + / Ctrl - e Ctrl 0 para voltar a 100%
        self.bind_all("<Control-MouseWheel>", lambda e: self.zoom(0.1 if e.delta > 0 else -0.1))
        self.bind_all("<Control-Button-4>", lambda e: self.zoom(0.1))
        self.bind_all("<Control-Button-5>", lambda e: self.zoom(-0.1))
        for tecla in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind_all(tecla, lambda e: self.zoom(0.1))
        for tecla in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind_all(tecla, lambda e: self.zoom(-0.1))
        self.bind_all("<Control-0>", lambda e: self.zoom(None))

        self.tela_chamados.recarregar()
        self.mostrar_tela("Novo chamado")

    def mostrar_tela(self, nome):
        mostrar, esconder = ((self.tela_novo, self.tela_chamados) if nome == "Novo chamado"
                             else (self.tela_chamados, self.tela_novo))
        esconder.grid_remove()
        mostrar.grid(row=0, column=0, sticky="nsew")
        for n, b in self.abas.items():
            b.configure(fg_color=tema.COR["topo_ativo"] if n == nome else "transparent",
                        text_color=tema.BRANCO if n == nome else tema.CINZA)

    def verificar_computador(self):
        """Roda a verificação em segundo plano e mostra o resultado."""
        self.avisar("Verificando o computador...")
        resultado = {}

        def rodar():
            resultado["itens"] = verificacao.verificar_tudo()

        def esperar():
            if "itens" in resultado:
                self.avisar("Verificação concluída.")
                JanelaVerificacao(self, resultado["itens"])
            else:
                self.after(200, esperar)

        threading.Thread(target=rodar, daemon=True).start()
        self.after(200, esperar)

    def avisar(self, texto):
        """Mensagens de sucesso aparecem na barra inferior (os erros usam caixa de diálogo)."""
        self.aviso.configure(text=f"{datetime.now():%H:%M}  {texto}")

    def _trocar_tema(self):
        escuro = bool(self.tema_escuro.get())
        customtkinter.set_appearance_mode("Dark" if escuro else "Light")
        tema.salvar_preferencia("tema", "escuro" if escuro else "claro")
        self._redesenhar()

    def _redesenhar(self):
        """Partes que não são CustomTkinter precisam ser refeitas ao trocar tema ou zoom."""
        tema.estilizar_ttk(self)
        for titulo in self.tela_novo.titulos + [self.tela_chamados.titulo]:
            titulo.desenhar()
        for entrada in list(CALENDARIOS):
            if entrada.winfo_exists():
                tema.ajustar_calendario(entrada)
        self.rodape.desenhar()
        self.tela_chamados.recarregar()

    def zoom(self, passo):
        novo = 1.0 if passo is None else round(min(tema.ZOOM_MAX, max(tema.ZOOM_MIN, tema.escala + passo)), 1)
        if novo != tema.escala:
            tema.escala = novo
            customtkinter.set_widget_scaling(novo)
            tema.salvar_preferencia("zoom", novo)
            self._redesenhar()
            self.rotulo_zoom.configure(text="" if novo == 1.0 else f"Zoom {round(novo * 100)}%")
        return "break"

    def report_callback_exception(self, exc, val, tb):
        logging.error("Erro não tratado na interface:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Erro inesperado", f"{val}\n\nO detalhe foi gravado no log do programa.")

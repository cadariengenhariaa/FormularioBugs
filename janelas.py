"""
Telas do Sistema de Chamados (versão 2.1).

Tudo acontece em uma única janela:
- TelaCarregamento ... abertura com barra de progresso por etapa;
- TelaNovoChamado .... abre o chamado e, na mesma tela, já define o responsável (cria a tarefa no FlowUp);
- TelaChamados ....... lista com filtros + painel de detalhes (triagem, excluir, exportar).

Os status são os mesmos do quadro do FlowUp (lidos na abertura).

As regras da integração ficam em servico.py; as cores e componentes, em tema.py.
Visão geral: docs/arquitetura.md
"""

import csv
import logging
import os
import shutil
import threading
import time
import unicodedata
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter
from tkcalendar import DateEntry

import tema
from config import PASTA_ANEXOS, VERSAO, carregar_config_flowup, resolver_caminho_dados, usuario_atual
from database import (atualizar_caminho_imagem_db, atualizar_chamado_db, buscar_chamado_por_protocolo,
                      buscar_todos_os_chamados, criar_tabela, registrar_chamado_db)
from servico import ErroIntegracao, carregar_status, excluir_chamado, sincronizar_tarefa
import verificacao

SEM_RESPONSAVEL = "Sem responsável (definir depois)"
# Categorias (softwares e Suporte TI) e os assuntos de cada uma.
# No banco continuam nas colunas "software" e "ferramenta".
FERRAMENTAS = {
    "Revit": ["Template", "Famílias", "Parâmetros", "Fórmulas", "Lookup table", "Vistas", "Licença", "Exportação",
              "Plug-ins", "Outros"],
    "Dynamo": ["Pacotes", "Rotinas", "Python", "Erros", "Outros"],
    "AutoCAD": ["CTB", "Layer", "Exportação", "Comandos", "Licença", "Outros"],
    "Office": ["Macros", "Fórmulas", "Validação de dados", "Mala direta", "Licença", "Outros"],
    "Suporte TI": ["Programas internos", "Sugestão de automação", "Instalação e atualização", "Acesso e permissões",
                   "Rede e VPN", "FlowUp", "Computador e periféricos", "E-mail e comunicação", "Licenças", "Outros"],
    "Outros": ["Outros"],
}


def chave_ordenacao(nome):
    texto = unicodedata.normalize("NFKD", nome or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def data_brasil(iso):
    """'2026-10-17' -> '17/10/2026'; '2026-10-17 09:30:00' -> '17/10/2026 09:30'."""
    if not iso:
        return ""
    try:
        if len(iso) > 10:
            return datetime.strptime(iso[:16], "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


CALENDARIOS = []  # campos de data abertos, para trocar tema e zoom


def seletor_data(pai):
    entrada = DateEntry(pai, locale="pt_BR", date_pattern="dd/MM/yyyy", width=12, borderwidth=0)
    tema.ajustar_calendario(entrada)
    CALENDARIOS.append(entrada)
    return entrada


# ---------------------------------------------------------------------------
# Tela de carregamento
# ---------------------------------------------------------------------------
class TelaCarregamento(customtkinter.CTkToplevel):
    """Abertura sem bordas: marca, etapa atual, porcentagem e barra dourada."""

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        largura, altura = 560, 300
        x = (self.winfo_screenwidth() - largura) // 2
        y = (self.winfo_screenheight() - altura) // 2
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        self.configure(fg_color=tema.COR["topo"])

        customtkinter.CTkLabel(self, text="", image=tema.imagem("marca_negativa.png", 72)).pack(pady=(58, 0))
        customtkinter.CTkFrame(self, height=2, fg_color=tema.DOURADO, corner_radius=0).pack(fill="x", padx=48,
                                                                                         pady=(30, 14))
        linha = customtkinter.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x", padx=48)
        self.etapa = customtkinter.CTkLabel(linha, text="Iniciando", text_color=tema.CINZA, font=tema.fonte(10))
        self.etapa.pack(side="left")
        self.porcento = customtkinter.CTkLabel(linha, text="0%", text_color=tema.CINZA, font=tema.fonte(10))
        self.porcento.pack(side="right")
        self.barra = customtkinter.CTkProgressBar(self, height=10, corner_radius=2, fg_color=tema.CINZA,
                                                  progress_color=tema.DOURADO)
        self.barra.set(0)
        self.barra.pack(fill="x", padx=48, pady=(4, 0))
        customtkinter.CTkLabel(self, text=f"Controle de Chamados  |  versão {VERSAO}", text_color="#8FA9B3",
                               font=tema.fonte(9)).pack(side="bottom", pady=12)
        self.demora = customtkinter.CTkLabel(self, text="", text_color=tema.DOURADO, font=tema.fonte(10),
                                             wraplength=460, justify="left")
        self.demora.pack(fill="x", padx=48, pady=(8, 0))
        self.valor = 0.0

    def mostrar(self, fracao, texto):
        """Anda a barra suavemente até a fração pedida."""
        self.etapa.configure(text=texto)
        self.valor = max(self.valor, min(fracao, 1.0))
        self.barra.set(self.valor)
        self.porcento.configure(text=f"{round(self.valor * 100)}%")


# ---------------------------------------------------------------------------
# Resultado da verificação do computador
# ---------------------------------------------------------------------------
class JanelaVerificacao(customtkinter.CTkToplevel):
    CORES = {verificacao.OK: ("#2E7D4F", "#7DC383"), verificacao.AVISO: ("#9A6B00", "#F2CF5B"),
             verificacao.ERRO: ("#8E2B2B", "#E08A84")}

    def __init__(self, master, itens):
        super().__init__(master)
        self.title("Verificação do computador")
        x = master.winfo_rootx() + max(0, (master.winfo_width() - 720) // 2)
        y = master.winfo_rooty() + max(0, (master.winfo_height() - 520) // 2)
        self.geometry(f"720x520+{x}+{y}")
        self.configure(fg_color=tema.COR["fundo"])
        self.transient(master)
        self.itens = itens
        titulo = tema.TituloSecao(self, "Verificação do computador")
        titulo.pack(anchor="w", padx=24, pady=(20, 8))
        erros = sum(1 for i in itens if i.situacao == verificacao.ERRO)
        avisos = sum(1 for i in itens if i.situacao == verificacao.AVISO)
        resumo = ("Tudo certo: este computador tem o que o programa precisa." if not erros and not avisos else
                  f"{erros} erro(s) e {avisos} aviso(s). Erros impedem o uso; avisos limitam a integração com o FlowUp.")
        tema.rotulo(self, resumo, 11, "texto", wraplength=660).pack(anchor="w", padx=24)
        lista = customtkinter.CTkScrollableFrame(self, fg_color=tema.COR["painel"], corner_radius=0)
        lista.pack(fill="both", expand=True, padx=24, pady=12)
        lista.grid_columnconfigure(1, weight=1)
        for linha, it in enumerate(itens):
            customtkinter.CTkLabel(lista, text=it.situacao, width=64, text_color=self.CORES[it.situacao],
                                   font=tema.fonte(11, "bold"), anchor="w").grid(row=linha, column=0, sticky="nw",
                                                                                 padx=(12, 6), pady=6)
            texto = f"{it.nome}\n{it.detalhe}" + (f"\nO que fazer: {it.dica}" if it.dica else "")
            tema.rotulo(lista, texto, 10, "texto", wraplength=540).grid(row=linha, column=1, sticky="w", pady=6)
        acoes = customtkinter.CTkFrame(self, fg_color="transparent")
        acoes.pack(fill="x", padx=24, pady=(0, 18))
        tema.botao(acoes, "Copiar relatório", self.copiar, width=150).pack(side="left")
        tema.botao(acoes, "Fechar", self.destroy, tipo="secundario", width=100).pack(side="left", padx=10)
        self.copiado = tema.rotulo(acoes, "", 9)
        self.copiado.pack(side="left", padx=8)
        self.after(100, self.lift)

    def copiar(self):
        self.clipboard_clear()
        self.clipboard_append(verificacao.relatorio_texto(self.itens))
        self.copiado.configure(text="Relatório copiado. Cole no chamado de Suporte TI.")


# ---------------------------------------------------------------------------
# Novo chamado (abertura + encaminhamento na mesma tela)
# ---------------------------------------------------------------------------
class TelaNovoChamado(customtkinter.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=tema.COR["fundo"])
        self.app = app
        self.caminho_anexo = None
        self.grid_columnconfigure((0, 1), weight=1, uniform="col")

        # --- Solicitação ---
        esq = customtkinter.CTkFrame(self, fg_color="transparent")
        esq.grid(row=0, column=0, sticky="nsew", padx=(32, 16), pady=(24, 8))
        esq.grid_columnconfigure(0, weight=1)
        self.titulos = [tema.TituloSecao(esq, "Solicitação")]
        self.titulos[0].grid(row=0, column=0, sticky="ew", pady=(0, 14))

        self.solicitante = self._campo_lista(esq, 1, "Solicitante", [])
        self.software = self._campo_lista(esq, 3, "Categoria", list(FERRAMENTAS), self._trocar_software)
        self.ferramenta = self._campo_lista(esq, 5, "Assunto", FERRAMENTAS["Revit"])
        tema.rotulo(esq, "Tema").grid(row=7, column=0, sticky="w", pady=(10, 2))
        self.tema = tema.campo(esq, placeholder_text="Resumo do problema em poucas palavras")
        self.tema.grid(row=8, column=0, sticky="ew")
        tema.rotulo(esq, "Descrição").grid(row=9, column=0, sticky="w", pady=(10, 2))
        self.descricao = tema.caixa_texto(esq, 150)
        self.descricao.grid(row=10, column=0, sticky="ew")
        linha_anexo = customtkinter.CTkFrame(esq, fg_color="transparent")
        linha_anexo.grid(row=11, column=0, sticky="ew", pady=(12, 0))
        tema.botao(linha_anexo, "Anexar imagem", self._anexar, tipo="secundario", width=150).pack(side="left")
        self.rotulo_anexo = tema.rotulo(linha_anexo, "Nenhuma imagem (opcional)", 9)
        self.rotulo_anexo.pack(side="left", padx=12)

        # --- Encaminhamento ---
        dir_ = customtkinter.CTkFrame(self, fg_color="transparent")
        dir_.grid(row=0, column=1, sticky="nsew", padx=(16, 32), pady=(24, 8))
        dir_.grid_columnconfigure(0, weight=1)
        self.titulos.append(tema.TituloSecao(dir_, "Encaminhamento"))
        self.titulos[1].grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.responsavel = self._campo_lista(dir_, 1, "Responsável", [SEM_RESPONSAVEL])
        tema.rotulo(dir_, "Data de entrega").grid(row=3, column=0, sticky="w", pady=(10, 2))
        self.entrega = seletor_data(dir_)
        self.entrega.grid(row=4, column=0, sticky="w")
        self.status = self._campo_lista(dir_, 5, "Status inicial", app.status_nomes)
        tema.rotulo(dir_, "Observações da triagem (opcional)").grid(row=7, column=0, sticky="w", pady=(10, 2))
        self.observacoes = tema.caixa_texto(dir_, 112)
        self.observacoes.grid(row=8, column=0, sticky="ew")
        tema.rotulo(dir_, "Com um responsável escolhido, a tarefa é criada no FlowUp ao registrar, já com a "
                          "descrição do chamado. Sem responsável, o chamado fica aguardando triagem.", 9,
                    wraplength=440).grid(row=9, column=0, sticky="w", pady=(12, 0))

        # --- Ações ---
        acoes = customtkinter.CTkFrame(self, fg_color="transparent")
        acoes.grid(row=1, column=0, columnspan=2, sticky="ew", padx=32, pady=(18, 24))
        tema.botao(acoes, "Registrar chamado", self.registrar, width=200).pack(side="left")
        tema.botao(acoes, "Limpar", self.limpar, tipo="secundario", width=110).pack(side="left", padx=12)
        self.mensagem = tema.rotulo(acoes, "", 10)
        self.mensagem.pack(side="left", padx=8)

    def _campo_lista(self, pai, linha, texto, valores, comando=None):
        tema.rotulo(pai, texto).grid(row=linha, column=0, sticky="w", pady=(10, 2))
        widget = tema.lista(pai, valores, command=comando, state="readonly")
        widget.grid(row=linha + 1, column=0, sticky="ew")
        if valores:
            widget.set(valores[0])
        return widget

    def atualizar_nomes(self, nomes):
        self.solicitante.configure(values=nomes)
        self.responsavel.configure(values=[SEM_RESPONSAVEL] + nomes)
        if self.solicitante.get() not in nomes:
            self.solicitante.set("Selecione seu nome")
        self.responsavel.set(SEM_RESPONSAVEL)

    def _trocar_software(self, software):
        opcoes = FERRAMENTAS.get(software, ["Outros"])
        self.ferramenta.configure(values=opcoes)
        self.ferramenta.set(opcoes[0])

    def _anexar(self):
        caminho = filedialog.askopenfilename(title="Selecionar imagem",
                                             filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp")])
        self.caminho_anexo = caminho or None
        self.rotulo_anexo.configure(text=os.path.basename(caminho) if caminho else "Nenhuma imagem (opcional)")

    def limpar(self):
        self.tema.delete(0, "end")
        self.descricao.delete("1.0", "end")
        self.observacoes.delete("1.0", "end")
        self.responsavel.set(SEM_RESPONSAVEL)
        self.status.set(self.app.status_nomes[0])
        self.entrega.set_date(date.today())
        self.caminho_anexo = None
        self.rotulo_anexo.configure(text="Nenhuma imagem (opcional)")

    def _copiar_anexo(self, protocolo):
        os.makedirs(PASTA_ANEXOS, exist_ok=True)
        nome = f"{protocolo}_{os.path.basename(self.caminho_anexo)}"
        shutil.copy(self.caminho_anexo, os.path.join(PASTA_ANEXOS, nome))
        return os.path.join("anexos", nome)

    def registrar(self):
        nome = self.solicitante.get()
        tema_txt = self.tema.get().strip()
        if nome not in self.app.nomes_map or not tema_txt:
            messagebox.showerror("Campos obrigatórios", "Escolha o seu nome na lista e preencha o tema do chamado.")
            return
        responsavel = self.responsavel.get()
        responsavel = "" if responsavel == SEM_RESPONSAVEL else responsavel

        protocolo = registrar_chamado_db(nome, self.software.get(), self.ferramenta.get(), tema_txt,
                                         self.descricao.get("1.0", "end-1c").strip())
        if not protocolo:
            messagebox.showerror("Erro no banco de dados",
                                 "Não foi possível registrar o chamado. Confira o acesso à pasta da rede.")
            return

        if self.caminho_anexo:
            try:
                atualizar_caminho_imagem_db(protocolo, self._copiar_anexo(protocolo))
            except OSError as e:
                logging.error("Anexo do %s não copiado: %s", protocolo, e)
                messagebox.showwarning("Anexo", f"O chamado {protocolo} foi registrado, mas a imagem não pôde "
                                                f"ser copiada para a rede.\n\n{e}")

        texto = f"Chamado {protocolo} registrado."
        if responsavel:
            entrega = self.entrega.get_date().strftime("%Y-%m-%d")
            atualizar_chamado_db(protocolo, nome, responsavel, entrega, self.status.get(),
                                 self.observacoes.get("1.0", "end-1c").strip(), usuario_atual())
            try:
                texto += " " + sincronizar_tarefa(protocolo, self.app.nomes_map)
            except ErroIntegracao as e:
                logging.error("Integração (%s): %s", protocolo, e)
                messagebox.showerror("Erro de integração",
                                     f"O chamado {protocolo} foi registrado, mas a tarefa não foi criada no FlowUp:"
                                     f"\n\n{e}\n\nAbra o chamado em Chamados e salve de novo para tentar outra vez.")
                texto += " Tarefa pendente no FlowUp."
        self.mensagem.configure(text=texto)
        self.limpar()
        self.app.tela_chamados.recarregar()


# ---------------------------------------------------------------------------
# Lista de chamados + detalhes
# ---------------------------------------------------------------------------
class TelaChamados(customtkinter.CTkFrame):
    COLUNAS = (("protocolo", "Protocolo", 80), ("tema", "Tema", 220), ("nome_solicitante", "Solicitante", 150),
               ("responsavel", "Responsável", 150), ("status", "Status", 110), ("data_hora", "Abertura", 125))

    def __init__(self, master, app):
        super().__init__(master, fg_color=tema.COR["fundo"], corner_radius=0)
        self.app = app
        self.atual = None
        self.dados = []
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2, minsize=460)
        self.grid_rowconfigure(1, weight=1)

        # --- Filtros ---
        filtros = customtkinter.CTkFrame(self, fg_color=tema.COR["painel"], corner_radius=0)
        filtros.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.busca = tema.campo(filtros, placeholder_text="Protocolo ou tema", width=200)
        self.busca.pack(side="left", padx=(32, 8), pady=12)
        self.busca.bind("<Return>", lambda e: self.recarregar())
        self.f_status = tema.lista(filtros, ["Todos os status"] + app.status_nomes, width=190, state="readonly")
        self.f_status.set("Todos os status")
        self.f_status.pack(side="left", padx=8)
        self.f_software = tema.lista(filtros, ["Todas as categorias"] + list(FERRAMENTAS), width=170, state="readonly")
        self.f_software.set("Todas as categorias")
        self.f_software.pack(side="left", padx=8)
        self.f_pessoa = tema.lista(filtros, ["Todas as pessoas"], width=200, state="readonly")
        self.f_pessoa.set("Todas as pessoas")
        self.f_pessoa.pack(side="left", padx=8)
        tema.botao(filtros, "Filtrar", self.recarregar, width=90).pack(side="left", padx=8)
        tema.botao(filtros, "Exportar CSV", self.exportar, tipo="secundario", width=120).pack(side="right", padx=32)

        # --- Lista ---
        caixa = customtkinter.CTkFrame(self, fg_color="transparent")
        caixa.grid(row=1, column=0, sticky="nsew", padx=(32, 12), pady=16)
        caixa.grid_rowconfigure(0, weight=1)
        caixa.grid_columnconfigure(0, weight=1)
        self.tabela = ttk.Treeview(caixa, columns=[c[0] for c in self.COLUNAS], show="headings",
                                   style="Cadari.Treeview", selectmode="browse")
        for chave, titulo, largura in self.COLUNAS:
            self.tabela.heading(chave, text=titulo, anchor="w")
            self.tabela.column(chave, width=largura, anchor="w", stretch=chave == "tema")
        rolagem = ttk.Scrollbar(caixa, orient="vertical", command=self.tabela.yview,
                                style="Cadari.Vertical.TScrollbar")
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        rolagem.grid(row=0, column=1, sticky="ns")
        self.tabela.bind("<<TreeviewSelect>>", self._selecionar)
        self.contagem = tema.rotulo(caixa, "", 9)
        self.contagem.grid(row=1, column=0, sticky="w", pady=(6, 0))

        # --- Detalhes ---
        self.detalhe = customtkinter.CTkScrollableFrame(self, fg_color=tema.COR["painel"], corner_radius=0)
        self.detalhe.grid(row=1, column=1, sticky="nsew", padx=(12, 32), pady=16)
        self.detalhe.grid_columnconfigure(0, weight=1)
        self._montar_detalhe()

    def _montar_detalhe(self):
        d = self.detalhe
        self.titulo = tema.TituloSecao(d, "Selecione um chamado", fundo="painel")
        self.titulo.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.resumo = tema.rotulo(d, "Escolha um chamado na lista para ver os detalhes.", 10, "texto",
                                  wraplength=420)
        self.resumo.grid(row=1, column=0, sticky="ew", padx=16)
        self.texto_desc = tema.caixa_texto(d, 110)
        self.texto_desc.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))
        self.imagem = customtkinter.CTkLabel(d, text="", cursor="hand2")
        self.imagem.grid(row=3, column=0, sticky="w", padx=16, pady=(8, 0))
        self.imagem.bind("<Button-1>", lambda e: self._abrir_imagem())

        self.designado = self._lista(d, 4, "Designado por")
        self.responsavel = self._lista(d, 6, "Responsável")
        tema.rotulo(d, "Data de entrega").grid(row=8, column=0, sticky="w", padx=16, pady=(10, 2))
        self.entrega = seletor_data(d)
        self.entrega.grid(row=9, column=0, sticky="w", padx=16)
        tema.rotulo(d, "Status").grid(row=10, column=0, sticky="w", padx=16, pady=(10, 2))
        self.status = tema.lista(d, self.app.status_nomes, state="readonly")
        self.status.grid(row=11, column=0, sticky="ew", padx=16)
        tema.rotulo(d, "Observações da triagem").grid(row=12, column=0, sticky="w", padx=16, pady=(10, 2))
        self.obs = tema.caixa_texto(d, 90)
        self.obs.grid(row=13, column=0, sticky="ew", padx=16)
        self.info_flowup = tema.rotulo(d, "", 9)
        self.info_flowup.grid(row=14, column=0, sticky="w", padx=16, pady=(8, 0))

        acoes = customtkinter.CTkFrame(d, fg_color="transparent")
        acoes.grid(row=15, column=0, sticky="ew", padx=16, pady=(12, 16))
        self.b_salvar = tema.botao(acoes, "Salvar", self.salvar, width=110)
        self.b_salvar.pack(side="left")
        self.b_excluir = tema.botao(acoes, "Excluir", self.excluir, tipo="perigo", width=90)
        self.b_excluir.pack(side="right")
        self._habilitar(False)

    def _lista(self, pai, linha, texto):
        tema.rotulo(pai, texto).grid(row=linha, column=0, sticky="w", padx=16, pady=(10, 2))
        w = tema.lista(pai, [], state="readonly")
        w.grid(row=linha + 1, column=0, sticky="ew", padx=16)
        return w

    # --- dados ---
    def atualizar_nomes(self, nomes):
        self.f_pessoa.configure(values=["Todas as pessoas"] + nomes)
        self.designado.configure(values=nomes)
        self.responsavel.configure(values=nomes)

    def _filtrados(self):
        status = self.f_status.get()
        software = self.f_software.get()
        pessoa = self.f_pessoa.get()
        busca = chave_ordenacao(self.busca.get().strip())
        linhas = buscar_todos_os_chamados(filtro_status=None if status.startswith("Todos") else status,
                                          filtro_software=None if software.startswith("Tod") else software)
        resultado = []
        for c in linhas:
            if not pessoa.startswith("Todas") and pessoa not in (c["nome_solicitante"], c["responsavel"]):
                continue
            if busca and busca not in chave_ordenacao(f"{c['protocolo']} {c['tema']}"):
                continue
            resultado.append(c)
        return resultado

    def recarregar(self, manter=None):
        manter = manter or (self.atual or {}).get("protocolo")
        self.dados = self._filtrados()
        self.tabela.delete(*self.tabela.get_children())
        for c in self.dados:
            valores = [c.get(k) or "" for k, _, _ in self.COLUNAS]
            valores[-1] = data_brasil(c.get("data_hora"))
            self.tabela.insert("", "end", iid=c["protocolo"], values=valores,
                               tags=("final",) if c.get("status") == self.app.status_final else ())
        self.tabela.tag_configure("final", foreground=tema.cor("texto_2"))
        self.contagem.configure(text=f"{len(self.dados)} chamado(s)")
        if manter and self.tabela.exists(manter):
            self.tabela.selection_set(manter)
            self.tabela.see(manter)
        else:
            self._limpar_detalhe()

    def _selecionar(self, _evento=None):
        selecao = self.tabela.selection()
        if selecao:
            self.mostrar(selecao[0])

    def mostrar(self, protocolo):
        c = buscar_chamado_por_protocolo(protocolo)
        if not c:
            return
        self.atual = c
        self._habilitar(True)  # campos desabilitados não aceitam valor novo
        self.titulo.texto = f"Chamado {protocolo}"
        self.titulo.desenhar()
        self.resumo.configure(text=f"{c['tema']}\n{c['software']} | {c['ferramenta']}\nAberto por "
                                   f"{c['nome_solicitante']} em {data_brasil(c['data_hora'])}")
        self.texto_desc.configure(state="normal")
        self.texto_desc.delete("1.0", "end")
        self.texto_desc.insert("1.0", c.get("descricao") or "(sem descrição)")
        self.texto_desc.configure(state="disabled")
        self.designado.set(c.get("designado_por") or c["nome_solicitante"])
        self.responsavel.set(c.get("responsavel") or "Selecione")
        try:
            self.entrega.set_date(datetime.strptime(c["data_entrega"], "%Y-%m-%d").date()
                                  if c.get("data_entrega") else date.today())
        except ValueError:
            self.entrega.set_date(date.today())
        self.status.set(c.get("status") or self.app.status_nomes[0])
        self.obs.delete("1.0", "end")
        self.obs.insert("1.0", c.get("observacoes") or "")
        tarefa = c.get("flowup_task_id")
        self.info_flowup.configure(text=f"Tarefa no FlowUp: {tarefa}" if tarefa else
                                   "Sem tarefa no FlowUp. Escolha o responsável e salve para criar.")
        self._mostrar_imagem(c.get("caminho_imagem"))
        self.b_excluir.configure(state="normal")

    def _mostrar_imagem(self, caminho):
        self.caminho_imagem = resolver_caminho_dados(caminho)
        if self.caminho_imagem and os.path.isfile(self.caminho_imagem):
            try:
                from PIL import Image
                im = Image.open(self.caminho_imagem)
                im.thumbnail((420, 220))
                self.imagem.configure(image=customtkinter.CTkImage(im, size=im.size), text="")
                return
            except Exception as e:
                logging.error("Erro ao abrir imagem: %s", e)
        self.imagem.configure(image=None, text="")

    def _abrir_imagem(self):
        if getattr(self, "caminho_imagem", None) and os.path.isfile(self.caminho_imagem) and hasattr(os, "startfile"):
            os.startfile(self.caminho_imagem)

    def _limpar_detalhe(self):
        self.atual = None
        self._habilitar(True)
        self.titulo.texto = "SELECIONE UM CHAMADO"
        self.titulo.desenhar()
        self.resumo.configure(text="Escolha um chamado na lista para ver os detalhes.")
        self.texto_desc.configure(state="normal")
        self.texto_desc.delete("1.0", "end")
        self.texto_desc.configure(state="disabled")
        self.obs.delete("1.0", "end")
        self.info_flowup.configure(text="")
        self.imagem.configure(image=None, text="")
        self._habilitar(False)
        self.b_excluir.configure(state="disabled")

    def _habilitar(self, ativo):
        estado = "normal" if ativo else "disabled"
        for w in (self.designado, self.responsavel, self.status):
            w.configure(state="readonly" if ativo else "disabled")
        self.b_salvar.configure(state=estado)
        self.entrega.configure(state=estado)
        self.obs.configure(state=estado)

    # --- ações ---
    def salvar(self):
        if not self.atual:
            return
        protocolo = self.atual["protocolo"]
        responsavel = self.responsavel.get()
        if responsavel not in self.app.nomes_map:
            messagebox.showerror("Responsável", "Escolha o responsável na lista. A tarefa do FlowUp precisa de um.")
            return
        ok = atualizar_chamado_db(protocolo, self.designado.get(), responsavel,
                                  self.entrega.get_date().strftime("%Y-%m-%d"), self.status.get(),
                                  self.obs.get("1.0", "end-1c").strip(), usuario_atual())
        if not ok:
            messagebox.showerror("Erro no banco de dados", "Não foi possível salvar o chamado.")
            return
        self._sincronizar(protocolo, f"Chamado {protocolo} salvo.")

    def _sincronizar(self, protocolo, prefixo):
        try:
            self.app.avisar(f"{prefixo} {sincronizar_tarefa(protocolo, self.app.nomes_map)}")
        except ErroIntegracao as e:
            logging.error("Integração (%s): %s", protocolo, e)
            self.app.avisar(f"{prefixo} Tarefa do FlowUp pendente.")
            messagebox.showerror("Erro de integração", f"{prefixo} Mas a integração com o FlowUp falhou:\n\n{e}\n\n"
                                                       "Depois de resolver, salve de novo para tentar outra vez.")
        self.recarregar(protocolo)

    def excluir(self):
        if not self.atual:
            return
        protocolo = self.atual["protocolo"]
        tarefa = self.atual.get("flowup_task_id")
        texto = f"Excluir definitivamente o chamado {protocolo} ({self.atual['tema']})?"
        if tarefa:
            texto += f"\n\nA tarefa {tarefa} também será excluída do FlowUp."
        if not messagebox.askyesno("Excluir chamado", texto + "\n\nEssa ação não pode ser desfeita.", icon="warning"):
            return
        try:
            self.app.avisar(excluir_chamado(protocolo))
        except ErroIntegracao as e:
            messagebox.showerror("Excluir chamado", str(e))
        self.atual = None
        self.recarregar()

    def exportar(self):
        if not self.dados:
            messagebox.showinfo("Exportar", "Não há chamados com os filtros atuais.")
            return
        caminho = filedialog.asksaveasfilename(defaultextension=".csv", title="Salvar relatório de chamados",
                                               filetypes=[("Arquivo CSV", "*.csv")])
        if not caminho:
            return
        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                cab = list(self.dados[0].keys())
                w.writerow(cab)
                for c in self.dados:
                    w.writerow([c[k] for k in cab])
            self.app.avisar(f"{len(self.dados)} chamado(s) exportado(s).")
        except OSError as e:
            messagebox.showerror("Exportar", f"Não foi possível salvar o arquivo:\n{e}")


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
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
            from config import resource_path
            self.iconbitmap(resource_path(os.path.join("matriz", "icone.ico")))
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
            from equipe import carregar_equipe
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
            from config import FLOWUP_PADRAO
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
        import traceback
        logging.error("Erro não tratado na interface:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Erro inesperado", f"{val}\n\nO detalhe foi gravado no log do programa.")

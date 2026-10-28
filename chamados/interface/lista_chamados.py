"""Aba "Chamados": lista com filtros e painel de detalhes (triagem, excluir e exportar)."""

import csv
import logging
import os
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter

from ..categorias import FERRAMENTAS
from ..config import resolver_caminho_dados, usuario_atual
from ..database import atualizar_chamado_db, buscar_chamado_por_protocolo, buscar_todos_os_chamados
from ..servico import ErroIntegracao, excluir_chamado, sincronizar_tarefa
from . import tema
from .comum import chave_ordenacao, data_brasil, seletor_data


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

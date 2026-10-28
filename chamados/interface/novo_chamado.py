"""Aba "Novo chamado": abertura e encaminhamento na mesma tela (cria a tarefa no FlowUp)."""

import logging
import os
import shutil
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter

from ..categorias import FERRAMENTAS
from ..config import PASTA_ANEXOS, usuario_atual
from ..database import atualizar_caminho_imagem_db, atualizar_chamado_db, registrar_chamado_db
from ..servico import ErroIntegracao, sincronizar_tarefa
from . import tema
from .comum import SEM_RESPONSAVEL, seletor_data


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

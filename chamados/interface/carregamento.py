"""Tela de carregamento: aparece enquanto o computador é verificado e os dados são lidos da rede."""

import customtkinter

from ..config import VERSAO
from . import tema


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

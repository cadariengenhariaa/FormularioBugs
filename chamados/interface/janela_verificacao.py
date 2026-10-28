"""Janela com o resultado da verificação do computador (botão "Verificar computador")."""

import customtkinter

from .. import verificacao
from . import tema


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

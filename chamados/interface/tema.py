"""
Identidade visual da Cadari aplicada às telas (cores, fonte, componentes, zoom e preferências).

Cores no formato (tema claro, tema escuro), que o CustomTkinter troca sozinho.
Regras deste programa (também registradas no guia de identidade visual):
- fonte Franklin Gothic Book; destaque em negrito, nunca itálico;
- tema escuro quase preto, com o dourado como cor de destaque;
- títulos de seção com a listra para tópicos (no escuro, só o check).
"""

import json
import os
import tempfile
import time
import tkinter as tk
import unicodedata
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter
from PIL import Image

from ..config import resource_path

AZUL = "#10475C"
AZUL_2 = "#17546C"
DOURADO = "#BCA985"
DOURADO_2 = "#AA9978"
CINZA = "#F1F2F2"
BRANCO = "#FFFFFF"

# (claro, escuro). O escuro é um azul quase preto, derivado do azul Cadari.
COR = {
    "fundo": (BRANCO, "#060D11"),
    "painel": (CINZA, "#0B161C"),
    "campo": (CINZA, "#101F27"),
    "campo_borda": ("#DADDDF", "#1C2F39"),
    "texto": (AZUL, "#E8ECED"),
    "texto_2": (AZUL_2, "#9FB1B8"),
    "borda": ("#C9CED2", "#1C2F39"),
    "primario": (AZUL, DOURADO),
    "primario_hover": (AZUL_2, DOURADO_2),
    "primario_texto": (BRANCO, "#060D11"),
    "secundario_hover": (CINZA, "#101F27"),
    "perigo": ("#8E2B2B", "#E08A84"),
    "listra": ("#C3D1D6", "#0B161C"),
    "listra_painel": ("#B9C7CC", "#0B161C"),
    "selecao": ("#DCE5E9", "#14303B"),
    "topo": (AZUL, "#08141A"),
    "topo_ativo": (AZUL_2, "#12252E"),
    "rodape_linha": (AZUL_2, "#0F2029"),
    "seta": ("#DCE5E9", DOURADO),          # botão da seta das listas (a seta usa a cor do texto)
    "seta_hover": ("#C3D1D6", DOURADO_2),
}

ZOOM_MIN, ZOOM_MAX = 0.8, 1.6

# Geometria do check da Cadari, medida no arquivo da marca (arquivo Cadari3.png da identidade visual).
# Coordenadas proporcionais à altura do check (altura = 1, largura = 0,92).
CHECK_PERNA_ESQUERDA = ((0.0, 0.50), (0.26, 0.50), (0.35, 0.72), (0.227, 1.0))   # dourado secundário
CHECK_PERNA_DIREITA = ((0.67, 0.0), (0.918, 0.0), (0.477, 1.0), (0.227, 1.0))    # dourado


def desenhar_check(canvas, x, y, altura):
    """Desenha o check da Cadari no Canvas com o canto superior esquerdo em (x, y)."""
    for pontos, preenchimento in ((CHECK_PERNA_ESQUERDA, DOURADO_2), (CHECK_PERNA_DIREITA, DOURADO)):
        coords = [v for px, py in pontos for v in (x + px * altura, y + py * altura)]
        canvas.create_polygon(*coords, fill=preenchimento, outline="")
escala = 1.0
_familia = None


# ---------------------------------------------------------------------------
# Preferências de cada pessoa (tema e zoom), gravadas no computador dela
# ---------------------------------------------------------------------------
ARQUIVO_PREF = os.path.join(os.getenv("LOCALAPPDATA") or tempfile.gettempdir(), "ControleChamados",
                            "preferencias.json")


def ler_preferencias():
    try:
        with open(ARQUIVO_PREF, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def salvar_preferencia(chave, valor):
    pref = ler_preferencias()
    pref[chave] = valor
    try:
        os.makedirs(os.path.dirname(ARQUIVO_PREF), exist_ok=True)
        with open(ARQUIVO_PREF, "w", encoding="utf-8") as f:
            json.dump(pref, f)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Básico
# ---------------------------------------------------------------------------
def familia():
    """Franklin Gothic Book (vem com o Office); sem ela, a alternativa mais próxima instalada."""
    global _familia
    if _familia is None:
        disponiveis = set(tkfont.families())
        for nome in ("Franklin Gothic Book", "Libre Franklin", "Franklin Gothic Medium", "Segoe UI", "Arial"):
            if nome in disponiveis:
                _familia = nome
                break
        else:
            _familia = "TkDefaultFont"
    return _familia


def fonte(tamanho=11, peso="normal"):
    """Fonte dos componentes CustomTkinter (o zoom já é aplicado pelo próprio CustomTkinter)."""
    return customtkinter.CTkFont(family=familia(), size=tamanho, weight=peso)


def fator():
    """Escala total da tela (DPI do Windows x zoom), a mesma que o CustomTkinter aplica."""
    try:
        return customtkinter.ScalingTracker.get_widget_scaling(tk._default_root)
    except Exception:
        return escala


def fonte_tk(tamanho=11, peso="normal"):
    """
    Fonte para widgets Tk/ttk comuns (tabela, calendário, títulos desenhados).
    Tamanho em pixels, como o CustomTkinter, para os textos ficarem iguais aos dos outros campos.
    """
    return (familia(), -max(8, round(tamanho * fator())), peso)


def escuro():
    return customtkinter.get_appearance_mode() == "Dark"


def cor(nome):
    """Cor atual (já resolvida para o tema em uso), para widgets que não são do CustomTkinter."""
    claro, esc = COR[nome]
    return esc if escuro() else claro


def imagem(nome, altura):
    """Imagem da pasta assets com altura fixa e largura proporcional (a marca nunca é distorcida)."""
    im = Image.open(resource_path(os.path.join("assets", nome)))
    largura = round(altura * im.width / im.height)
    return customtkinter.CTkImage(light_image=im, dark_image=im, size=(largura, altura))


def chave_texto(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
def botao(pai, texto, comando, tipo="primario", **kw):
    if tipo == "primario":
        return customtkinter.CTkButton(pai, text=texto, command=comando, height=38, corner_radius=4,
                                       fg_color=COR["primario"], hover_color=COR["primario_hover"],
                                       text_color=COR["primario_texto"], font=fonte(11, "bold"), **kw)
    cor_texto = COR["perigo"] if tipo == "perigo" else COR["texto"]
    return customtkinter.CTkButton(pai, text=texto, command=comando, height=38, corner_radius=4,
                                   fg_color="transparent", hover_color=COR["secundario_hover"],
                                   border_width=1, border_color=cor_texto, text_color=cor_texto,
                                   font=fonte(11, "bold"), **kw)


def rotulo(pai, texto, tamanho=10, cor_nome="texto_2", peso="normal", **kw):
    return customtkinter.CTkLabel(pai, text=texto, text_color=COR[cor_nome], font=fonte(tamanho, peso),
                                  anchor="w", justify="left", **kw)


def campo(pai, **kw):
    return customtkinter.CTkEntry(pai, height=36, corner_radius=4, border_width=1, fg_color=COR["campo"],
                                  border_color=COR["campo_borda"], text_color=COR["texto"], font=fonte(11), **kw)


def lista(pai, valores, **kw):
    combo = customtkinter.CTkComboBox(pai, values=valores, height=36, corner_radius=4, border_width=1,
                                      fg_color=COR["campo"], border_color=COR["campo_borda"],
                                      button_color=COR["seta"], button_hover_color=COR["seta_hover"],
                                      text_color=COR["texto"], font=fonte(11), dropdown_font=fonte(11),
                                      dropdown_fg_color=COR["fundo"], dropdown_text_color=COR["texto"],
                                      dropdown_hover_color=COR["selecao"], **kw)
    ativar_navegacao(combo)
    return combo


def _escolher(combo, valor):
    combo.set(valor)
    comando = getattr(combo, "_command", None)
    if comando:
        comando(valor)


def navegar(combo, passo):
    """Vai para o item anterior (-1) ou seguinte (+1) da lista."""
    if str(combo.cget("state")) == "disabled":
        return
    valores = list(combo.cget("values"))
    if not valores:
        return
    atual = combo.get()
    i = valores.index(atual) if atual in valores else -1
    _escolher(combo, valores[max(0, min(len(valores) - 1, i + passo))])


def digitar(combo, letra):
    """
    Pré-seleciona o primeiro item que começa com o que foi digitado (sem acento, sem maiúscula).
    Letras digitadas em sequência rápida formam o começo do nome; a mesma letra repetida
    passa para o próximo nome com essa inicial.
    """
    if str(combo.cget("state")) == "disabled" or not letra.isprintable() or not letra.strip():
        return
    agora = time.monotonic()
    busca = getattr(combo, "_busca", "")
    busca = busca + chave_texto(letra) if agora - getattr(combo, "_busca_t", 0) < 0.8 else chave_texto(letra)
    combo._busca, combo._busca_t = busca, agora
    valores = list(combo.cget("values"))
    atual = combo.get()
    inicio = valores.index(atual) + 1 if atual in valores else 0
    if len(busca) > 1 and len(set(busca)) == 1:
        busca = busca[0]  # mesma letra repetida: próximo nome com essa inicial
    ordem = valores[inicio:] + valores[:inicio] if len(busca) == 1 else valores
    for v in ordem:
        if chave_texto(v).startswith(busca):
            _escolher(combo, v)
            return


def ativar_navegacao(combo):
    """Rolagem do mouse troca o item; teclas pré-selecionam; setas sobem e descem."""
    def rolar(evento):
        if evento.state & 0x4:  # Ctrl + rolagem é o zoom
            return None
        delta = evento.delta if evento.delta else (120 if evento.num == 4 else -120)
        navegar(combo, -1 if delta > 0 else 1)
        return "break"

    def tecla(evento):
        if evento.keysym in ("Up", "Down"):
            navegar(combo, -1 if evento.keysym == "Up" else 1)
            return "break"
        if evento.keysym in ("Tab", "ISO_Left_Tab", "Return", "Escape"):
            return None
        digitar(combo, evento.char or "")
        return "break"

    for w in (combo._entry, combo._canvas):
        w.bind("<MouseWheel>", rolar, add="+")
        w.bind("<Button-4>", rolar, add="+")
        w.bind("<Button-5>", rolar, add="+")
    combo._entry.bind("<KeyPress>", tecla, add="+")
    combo._entry.bind("<Button-1>", lambda e: combo._entry.focus_set(), add="+")


def caixa_texto(pai, altura=110, **kw):
    return customtkinter.CTkTextbox(pai, height=altura, corner_radius=4, border_width=1, fg_color=COR["campo"],
                                    border_color=COR["campo_borda"], text_color=COR["texto"], font=fonte(11),
                                    wrap="word", **kw)


def cores_calendario():
    """Cores do calendário (tkcalendar) para o tema atual."""
    if escuro():
        return dict(background="#08141A", foreground=CINZA, bordercolor="#1C2F39",
                    headersbackground="#0B161C", headersforeground=DOURADO,
                    normalbackground="#060D11", normalforeground="#E8ECED",
                    weekendbackground="#060D11", weekendforeground="#E8ECED",
                    othermonthbackground="#0B161C", othermonthforeground="#5E737C",
                    othermonthwebackground="#0B161C", othermonthweforeground="#5E737C",
                    selectbackground=DOURADO, selectforeground="#060D11")
    return dict(background=AZUL, foreground=BRANCO, bordercolor="#C9CED2",
                headersbackground=CINZA, headersforeground=AZUL,
                normalbackground=BRANCO, normalforeground=AZUL,
                weekendbackground=BRANCO, weekendforeground=AZUL,
                othermonthbackground=CINZA, othermonthforeground="#8A9AA1",
                othermonthwebackground=CINZA, othermonthweforeground="#8A9AA1",
                selectbackground=DOURADO, selectforeground=AZUL)


def ajustar_calendario(entrada):
    """Aplica fonte e cores do tema atual a um DateEntry (campo e calendário que abre)."""
    st = ttk.Style(entrada)
    try:
        existe = bool(st.layout("Cadari.DateEntry"))
    except tk.TclError:
        existe = False
    if not existe:
        st.layout("Cadari.DateEntry", st.layout("DateEntry"))
    entrada.configure(font=fonte_tk(11), style="Cadari.DateEntry")
    entrada._calendar.configure(font=fonte_tk(12), **cores_calendario())


class TituloSecao(tk.Canvas):
    """
    Título de seção com a listra para tópicos: check dourado + faixa translúcida azul
    e o título em caixa alta e negrito sobre a faixa. No tema escuro a faixa some
    (regra do guia: sobre fundo escuro, só o check).
    """

    ALTURA = 34

    def __init__(self, pai, texto, fundo="fundo"):
        super().__init__(pai, height=self.ALTURA, highlightthickness=0, bd=0)
        self.texto = texto
        self.fundo = fundo
        self.bind("<Configure>", lambda e: self.desenhar())

    def desenhar(self):
        self.delete("all")
        h = round(self.ALTURA * fator())
        self.configure(bg=cor(self.fundo), height=h)
        f = fonte_tk(19, "bold")
        x_texto = round(1.2 * h)
        largura = max(round(5.04 * h), x_texto + tkfont.Font(font=f).measure(self.texto.upper()) + round(0.6 * h))
        if not escuro():
            # faixa com a mesma inclinação da perna direita do check, logo depois dela
            self.create_polygon(round(0.54 * h), h, round(0.98 * h), 0, largura, 0, largura, h,
                                fill=cor("listra_painel" if self.fundo == "painel" else "listra"), outline="")
        desenhar_check(self, 0, 0, h)
        if int(self.cget("width")) != largura:
            self.configure(width=largura)
        self.create_text(x_texto, h // 2 + 1, text=self.texto.upper(), anchor="w", font=f, fill=cor("texto"))


class Rodape(tk.Canvas):
    """Faixa com linhas diagonais finas e a assinatura (check) à direita."""

    def __init__(self, pai, altura=34):
        super().__init__(pai, height=altura, highlightthickness=0, bd=0)
        self.altura = altura
        self.bind("<Configure>", lambda e: self.desenhar())

    def desenhar(self):
        self.delete("all")
        largura, h = self.winfo_width(), self.altura
        self.configure(bg=cor("topo"))
        for x in range(-h, largura + h, 7):
            self.create_line(x, h, x + h, 0, fill=cor("rodape_linha"), width=1)
        a = 18
        desenhar_check(self, largura - 22 - 0.92 * a, (h - a) / 2, a)


def estilizar_ttk(raiz):
    """Estilo da tabela de chamados, da rolagem e do campo de data para o tema e o zoom atuais."""
    st = ttk.Style(raiz)
    st.theme_use("clam")
    st.configure(".", font=fonte_tk(12))  # cabeçalhos do calendário e demais textos ttk
    st.configure("Cadari.Treeview", background=cor("fundo"), fieldbackground=cor("fundo"),
                 foreground=cor("texto"), rowheight=round(30 * fator()), borderwidth=0, font=fonte_tk(13))
    st.map("Cadari.Treeview", background=[("selected", cor("selecao"))], foreground=[("selected", cor("texto"))])
    st.configure("Cadari.Treeview.Heading", background=cor("painel"), foreground=cor("texto"),
                 relief="flat", borderwidth=0, font=fonte_tk(13, "bold"))
    st.map("Cadari.Treeview.Heading", background=[("active", cor("selecao"))])
    st.layout("Cadari.Treeview", [("Cadari.Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Cadari.Vertical.TScrollbar", background=cor("painel"), troughcolor=cor("fundo"),
                 bordercolor=cor("fundo"), arrowcolor=cor("texto_2"))
    # Campo de data com a mesma cara dos outros campos
    st.configure("Cadari.DateEntry", fieldbackground=cor("campo"), background=cor("campo"),
                 foreground=cor("texto"), bordercolor=cor("campo_borda"), lightcolor=cor("campo"),
                 darkcolor=cor("campo"), arrowcolor=cor("texto"), insertcolor=cor("texto"), padding=6)
    st.map("Cadari.DateEntry", fieldbackground=[("disabled", cor("painel"))],
           foreground=[("disabled", cor("texto_2"))], bordercolor=[("focus", DOURADO)])

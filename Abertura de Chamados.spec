# -*- mode: python ; coding: utf-8 -*-
#
# Receita de compilação do "Abertura de Chamados.exe" (PyInstaller, arquivo único).
#
# Na pasta do projeto, com o ambiente virtual ativado:
#     pyinstaller --clean --noconfirm "Abertura de Chamados.spec"
#
# O executável sai em dist\Abertura de Chamados.exe.
# Não apague este arquivo: ele é a fonte da compilação (ver docs/desenvolvimento-e-distribuicao.md).

import os

PASTA_PROJETO = SPECPATH  # pasta deste .spec, definida pelo PyInstaller
ICONE = os.path.join(PASTA_PROJETO, 'assets', 'icone.ico')
TELA_ABERTURA = os.path.join(PASTA_PROJETO, 'assets', 'tela_abertura.png')

a = Analysis(
    [os.path.join(PASTA_PROJETO, 'main.py')],
    pathex=[PASTA_PROJETO],
    binaries=[],
    datas=[(os.path.join(PASTA_PROJETO, 'assets'), 'assets')],
    # babel.numbers: exigido pelo tkcalendar.
    # PIL._tkinter_finder: só faz falta se compilar fora do Windows; no Windows não atrapalha.
    hiddenimports=['babel.numbers', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
# Tela de abertura do PyInstaller: exige Tcl/Tk "threaded", que o Python 3.14 (Tcl/Tk 9) não tem.
# Nesse caso o exe sai sem ela e o programa mostra só a própria tela de carregamento.
import sys
extras_splash = []
if sys.version_info < (3, 14):
    splash = Splash(
        TELA_ABERTURA,
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )
    extras_splash = [splash, splash.binaries]

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    *extras_splash,
    [],
    name='Abertura de Chamados',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICONE],
)

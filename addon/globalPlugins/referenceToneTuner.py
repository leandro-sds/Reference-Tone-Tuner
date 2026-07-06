import os
import winsound
import wx

import addonHandler
import globalPluginHandler
import gui
import scriptHandler
import ui
from logHandler import log

addonHandler.initTranslation()

ADDON_TITLE = _("Reference Tone Tuner")
ADDON_CATEGORY = _("Reference Tone Tuner")

# Renomeado de "STRINGS" para "CORDAS": o nome antigo era ambíguo
# (parecia se referir a strings de texto, e não a cordas do violão).
CORDAS = [
    (_("1ª corda (Mi agudo)"), "1e.WAV"),
    (_("2ª corda (Si)"), "2B.WAV"),
    (_("3ª corda (Sol)"), "3G.WAV"),
    (_("4ª corda (Ré)"), "4D.WAV"),
    (_("5ª corda (Lá)"), "5A.WAV"),
    (_("6ª corda (Mi grave)"), "6E.WAV"),
]

ACORDE_SOL = "Sol.WAV"
ACORDE_MI = "Mi.WAV"

# Intervalo padrão do loop (em milissegundos) e limites de ajuste.
LOOP_INTERVAL_PADRAO_MS = 2000
LOOP_INTERVAL_MIN_MS = 1000
LOOP_INTERVAL_MAX_MS = 10000
LOOP_INTERVAL_PASSO_MS = 250


def _pasta_arquivos():
    basePath = os.path.dirname(__file__)
    return os.path.join(basePath, "cordas")


class JanelaAjuda(wx.Dialog):
    def __init__(self, parent):
        super(JanelaAjuda, self).__init__(
            parent,
            title=_("Ajuda - Atalhos do teclado"),
            size=(480, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        lblInfo = wx.StaticText(self, label=_("Comandos disponíveis:"))
        mainSizer.Add(lblInfo, 0, wx.ALL, 10)

        self.listCtrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.listCtrl.InsertColumn(0, _("Tecla"), width=120)
        self.listCtrl.InsertColumn(1, _("Ação"), width=330)

        atalhos = [
            ("1–6", _("Toca uma corda (1=Mi agudo … 6=Mi grave)")),
            ("T", _("Toca todas as cordas (da 6ª para a 1ª)")),
            ("S", _("Toca o acorde de Sol maior")),
            ("M", _("Toca o acorde de Mi maior")),
            ("R", _("Ativa/desativa a repetição em loop")),
            ("A", _("Aumenta o intervalo do loop")),
            ("D", _("Diminui o intervalo do loop")),
            ("F1", _("Mostra esta ajuda")),
            ("Esc", _("Para o som / Fecha a janela")),
            ("Alt+F4", _("Sai")),
        ]

        for i, (tecla, acao) in enumerate(atalhos):
            self.listCtrl.InsertItem(i, tecla)
            self.listCtrl.SetItem(i, 1, acao)

        mainSizer.Add(self.listCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.btnClose = wx.Button(self, wx.ID_CANCEL, label=_("&Fechar"))
        mainSizer.Add(self.btnClose, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.Bind(wx.EVT_BUTTON, self._fechar, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._fechar_evento)

        self.SetEscapeId(wx.ID_CANCEL)
        accel_tbl = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CANCEL)])
        self.SetAcceleratorTable(accel_tbl)

        self.listCtrl.Bind(wx.EVT_KEY_DOWN, self._tecla_lista)

        self.SetSizer(mainSizer)
        self.Centre()
        self.listCtrl.SetFocus()

    def _tecla_lista(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _fechar(self, event):
        self.Destroy()

    def _fechar_evento(self, event):
        self.Destroy()


class JanelaAfinador(wx.Dialog):
    def __init__(self, parent):
        super(JanelaAfinador, self).__init__(
            parent, title=ADDON_TITLE, style=wx.DEFAULT_DIALOG_STYLE
        )

        self.pastaSons = _pasta_arquivos()
        self.janelaAjuda = None

        # Intervalo (ms) usado ao repetir uma sequência em loop.
        # Ao tocar uma nota/acorde único, soma-se 1000ms a este valor,
        # para dar um respiro maior entre repetições de um som isolado.
        self.loopIntervalMs = LOOP_INTERVAL_PADRAO_MS

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tick, self.timer)

        self.fila = []
        self.indice = 0

        self.Bind(wx.EVT_CLOSE, self._ao_fechar)
        self.Bind(wx.EVT_CHAR_HOOK, self._capturar_teclas)

        pnl = wx.Panel(self)
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            pnl,
            label=_("Pressione F1 para ver a lista de atalhos disponíveis."),
        )
        mainSizer.Add(info, 0, wx.ALL, 10)

        self.chkLoop = wx.CheckBox(pnl, label=_("&Repetir em loop"))
        self.chkLoop.Bind(wx.EVT_CHECKBOX, self._ao_mudar_loop)
        mainSizer.Add(self.chkLoop, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # O rótulo de intervalo começa vazio de propósito: só é preenchido
        # (e só é falado) quando o usuário efetivamente ajusta o valor com
        # A/D, para não sobrecarregar o usuário de informação logo ao abrir
        # a janela.
        self.lblIntervalo = wx.StaticText(pnl, label="")
        mainSizer.Add(self.lblIntervalo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btnRow = wx.BoxSizer(wx.HORIZONTAL)

        self.btnHelp = wx.Button(pnl, label=_("Ajuda (F1)"))
        self.btnHelp.Bind(wx.EVT_BUTTON, self._mostrar_ajuda)
        btnRow.Add(self.btnHelp, 0, wx.RIGHT, 10)

        btnClose = wx.Button(pnl, wx.ID_CLOSE, label=_("&Fechar"))
        btnClose.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
        btnRow.Add(btnClose, 0)

        mainSizer.Add(btnRow, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        pnl.SetSizer(mainSizer)
        mainSizer.Fit(self)
        self.Centre()

        wx.CallLater(100, self.chkLoop.SetFocus)

    def _texto_intervalo(self):
        return _("Intervalo do loop: {0:.1f} segundos (use A / D para ajustar)").format(
            self.loopIntervalMs / 1000
        )

    def _mostrar_ajuda(self, evt=None):
        if self.janelaAjuda:
            try:
                if self.janelaAjuda.IsShown():
                    self.janelaAjuda.Raise()
                    self.janelaAjuda.listCtrl.SetFocus()
                    return
            except Exception:
                self.janelaAjuda = None
        self.janelaAjuda = JanelaAjuda(self)
        self.janelaAjuda.Show()

    def _ao_mudar_loop(self, event):
        if self.chkLoop.GetValue():
            ui.message(
                _("Loop ativado. Pressione A para aumentar o intervalo ou D para diminuir.")
            )
        else:
            ui.message(_("Loop desativado"))
            self._parar()

    def _ajustar_intervalo_loop(self, delta):
        anterior = self.loopIntervalMs
        self.loopIntervalMs = max(
            LOOP_INTERVAL_MIN_MS, min(LOOP_INTERVAL_MAX_MS, self.loopIntervalMs + delta)
        )
        self.lblIntervalo.SetLabel(self._texto_intervalo())

        segundos = self.loopIntervalMs / 1000
        if self.loopIntervalMs == anterior:
            ui.message(
                _("Intervalo do loop já está no limite: {0:.1f} segundos").format(segundos)
            )
        else:
            ui.message(_("Intervalo do loop: {0:.1f} segundos").format(segundos))

    def _capturar_teclas(self, event):
        key = event.GetKeyCode()

        if key == wx.WXK_ESCAPE:
            if self.fila or self.timer.IsRunning():
                self._parar()
                ui.message(_("Parado"))
            else:
                self.Close()
            return

        if key == wx.WXK_F4 and event.AltDown():
            self.Close()
            return

        if key == wx.WXK_F1:
            self._mostrar_ajuda()
            return

        if key == ord("R"):
            self.chkLoop.SetValue(not self.chkLoop.GetValue())
            self._ao_mudar_loop(None)
            return

        if key == ord("A"):
            self._ajustar_intervalo_loop(LOOP_INTERVAL_PASSO_MS)
            return

        if key == ord("D"):
            self._ajustar_intervalo_loop(-LOOP_INTERVAL_PASSO_MS)
            return

        if key == ord("T"):
            self._tocar_todas()
            return

        if key == ord("S"):
            self._iniciar([ACORDE_SOL])
            return

        if key == ord("M"):
            self._iniciar([ACORDE_MI])
            return

        if ord("1") <= key <= ord("6"):
            idx = key - ord("1")
            self._iniciar([idx])
            return

        teclasPermitidas = [
            wx.WXK_TAB,
            wx.WXK_RETURN,
            wx.WXK_NUMPAD_ENTER,
            wx.WXK_SPACE,
            wx.WXK_UP,
            wx.WXK_DOWN,
            wx.WXK_LEFT,
            wx.WXK_RIGHT,
            wx.WXK_HOME,
            wx.WXK_END,
            wx.WXK_PAGEUP,
            wx.WXK_PAGEDOWN,
            wx.WXK_DELETE,
            wx.WXK_BACK,
        ]

        if key in teclasPermitidas:
            event.Skip()
            return
        return

    def _tocar_todas(self):
        self._iniciar([5, 4, 3, 2, 1, 0])

    def _iniciar(self, lista):
        self._parar()
        self.fila = lista
        self.indice = 0
        self._passo()

    def _passo(self):
        if not self.fila:
            return

        if self.indice < len(self.fila):
            item = self.fila[self.indice]
            if isinstance(item, int):
                arquivo = CORDAS[item][1]
            else:
                arquivo = item

            if self._tocar_arquivo(arquivo):
                if self.indice < len(self.fila) - 1:
                    self.indice += 1
                    self.timer.Start(1000, wx.TIMER_ONE_SHOT)
                else:
                    if self.chkLoop.GetValue():
                        self.indice = 0
                        self.timer.Start(self.loopIntervalMs, wx.TIMER_ONE_SHOT)
                    else:
                        # CORREÇÃO: antes a fila não era limpa aqui. Isso fazia
                        # com que, após tocar uma corda/acorde único sem loop,
                        # self.fila continuasse com um item "fantasma" mesmo
                        # com a reprodução já concluída. Consequência prática:
                        # o próximo Esc entendia (erradamente) que ainda havia
                        # algo tocando e apenas exibia "Parado" em vez de
                        # fechar a janela. Aqui limpamos apenas o estado da
                        # fila, sem chamar self._parar() (que faria
                        # SND_PURGE e cortaria o som que acabou de iniciar).
                        self.fila = []
                        self.indice = 0
            else:
                self._parar()

    def _tick(self, event):
        self._passo()

    def _tocar_arquivo(self, arquivo):
        caminho = os.path.join(self.pastaSons, arquivo)
        if not os.path.isfile(caminho):
            log.error(f"Arquivo de som não encontrado: {caminho}")
            return False

        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        try:
            winsound.PlaySound(caminho, flags)
            return True
        except Exception as e:
            log.error(f"Erro ao tocar som: {e}")
            return False

    def _parar(self):
        self.timer.Stop()
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.fila = []
        self.indice = 0

    def _ao_fechar(self, event):
        self._parar()
        if self.janelaAjuda:
            try:
                self.janelaAjuda.Destroy()
            except Exception:
                pass
        self.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self, *args, **kwargs):
        super(GlobalPlugin, self).__init__(*args, **kwargs)
        self._adicionar_menu()

    def _adicionar_menu(self):
        try:
            toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
            self.menuItem = toolsMenu.Append(wx.ID_ANY, ADDON_TITLE)
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._abrir, self.menuItem)
        except Exception as e:
            log.error(f"Erro ao adicionar item de menu: {e}")

    def terminate(self):
        try:
            toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
            toolsMenu.Remove(self.menuItem)
        except Exception:
            pass

        # CORREÇÃO: se o addon for recarregado/desativado com a janela do
        # afinador aberta, o timer e o som em reprodução ficavam "órfãos"
        # (a janela continuava existindo e o timer continuava disparando
        # mesmo com o GlobalPlugin já finalizado). Agora fechamos qualquer
        # janela aberta, o que também para o timer e purga o som via
        # _ao_fechar -> _parar().
        try:
            for child in list(gui.mainFrame.Children):
                if isinstance(child, JanelaAfinador):
                    child.Close()
        except Exception as e:
            log.error(f"Erro ao fechar janela do afinador durante terminate: {e}")

    @scriptHandler.script(
        category=ADDON_CATEGORY,
        description=_("Abre a janela do Reference Tone Tuner."),
        gesture="kb:NVDA+shift+v",
    )
    def script_openTuner(self, gesture):
        self._abrir(None)

    def _abrir(self, evt):
        for child in gui.mainFrame.Children:
            if isinstance(child, JanelaAfinador):
                child.Raise()
                wx.CallLater(100, child.chkLoop.SetFocus)
                return

        dlg = JanelaAfinador(gui.mainFrame)
        dlg.Show()
        dlg.Raise()
        wx.CallLater(100, dlg.chkLoop.SetFocus)

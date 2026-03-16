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

STRINGS = [
    (_("1ª corda (Mi agudo)"), "1e.WAV"),
    (_("2ª corda (Si)"), "2B.WAV"),
    (_("3ª corda (Sol)"), "3G.WAV"),
    (_("4ª corda (Ré)"), "4D.WAV"),
    (_("5ª corda (Lá)"), "5A.WAV"),
    (_("6ª corda (Mi grave)"), "6E.WAV"),
]

ACORDE_SOL = "Sol.WAV"
ACORDE_MI = "Mi.WAV"


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
            label=_("Use as teclas 1 a 6 para tocar as cordas, ou pressione F1 para ajuda."),
        )
        mainSizer.Add(info, 0, wx.ALL, 10)

        self.chkLoop = wx.CheckBox(pnl, label=_("&Repetir em loop (R)"))
        self.chkLoop.Bind(wx.EVT_CHECKBOX, self._ao_mudar_loop)
        mainSizer.Add(self.chkLoop, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

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
        if not self.chkLoop.GetValue():
            self._parar()

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
            estado = self.chkLoop.GetValue()
            novo = not estado
            self.chkLoop.SetValue(novo)
            ui.message(_("Loop ativado") if novo else _("Loop desativado"))
            if not novo:
                self._parar()
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

        modoSequencia = len(self.fila) > 1

        if self.indice < len(self.fila):
            item = self.fila[self.indice]
            if isinstance(item, int):
                arquivo = STRINGS[item][1]
            else:
                arquivo = item

            if self._tocar_arquivo(arquivo):
                if self.indice < len(self.fila) - 1:
                    self.indice += 1
                    self.timer.Start(1000, wx.TIMER_ONE_SHOT)
                else:
                    if self.chkLoop.GetValue():
                        self.indice = 0
                        self.timer.Start(3000 if modoSequencia else 4000, wx.TIMER_ONE_SHOT)
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

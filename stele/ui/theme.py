"""Stele's graphite / copper desktop design system. Presentation only."""
from pathlib import Path
from PySide6.QtCore import QEvent, QObject, Qt
from shiboken6 import isValid
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget

_TEMPLATE = """
QMainWindow, QWidget {{ background: {bg}; color: {text}; font-family: "Segoe UI"; font-size: 13px; }}
QWidget#sidebar {{ background: {sidebar}; border-right: 1px solid {line}; }}
QLabel {{ background: transparent; }}
QLabel#brand {{ color: {textStrong}; font-size: 22px; font-weight: 700; letter-spacing: 3px; }}
QLabel#brandNote {{ color: {textFaint}; font-size: 11px; }}
QLabel#eyebrow {{ color: {eyebrow}; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
QLabel#pageTitle {{ color: {title}; font-size: 28px; font-weight: 600; }}
QLabel#pageSubtitle {{ color: {muted}; font-size: 13px; }}
QWidget#pageHeader {{ border-bottom: 1px solid {line}; }}
QLabel#edition {{ color: {chipText}; background: {chipBg}; border: 1px solid {chipLine}; border-radius: 6px; padding: 6px 12px; font-size: 11px; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; padding: 4px 12px; }}
QListWidget#nav::item {{ color: {navText}; padding: 13px 14px; margin: 3px 0; border-radius: 7px; }}
QListWidget#nav::item:hover {{ background: {navHover}; color: {navHoverText}; }}
QListWidget#nav::item:selected {{ background: {navSel}; color: {accentText}; border-left: 3px solid {accentLine}; }}
QPushButton {{ background: {btn}; color: {btnText}; border: 1px solid {field_line}; border-radius: 6px; padding: 8px 14px; font-weight: 500; }}
QPushButton:hover {{ background: {btnHover}; border-color: {btnHoverLine}; }}
QPushButton:pressed {{ background: {btnPressed}; }}
QPushButton:focus {{ border: 2px solid {accentLine}; }}
QPushButton:disabled {{ background: {btnDisabled}; color: {disabledText}; border-color: {disabledLine}; }}
QPushButton#primary {{ background: {accent}; color: {bg}; border-color: {accent}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {accentHover}; border-color: {accentHover}; }}
QPushButton#primary:pressed {{ background: {accentPressed}; }}
QPushButton#primary:disabled {{ background: {primaryDisabled}; color: {primaryDisabledText}; border-color: {primaryDisabledLine}; }}
QPushButton#gear {{ background: transparent; color: {gearText}; text-align: left; border-color: {disabledLine}; margin: 12px; }}
QLineEdit, QComboBox, QSpinBox {{ background: {field}; border: 1px solid {field_line}; border-radius: 5px; padding: 8px 10px; min-height: 18px; selection-background-color: {accent}; selection-color: {bg}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {accentLine}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url(CHEVRON_ASSET); width: 12px; height: 12px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 24px; border-left: 1px solid {field_line}; }}
QSpinBox::up-arrow {{ image: url(UP_ASSET); width: 12px; height: 12px; }}
QSpinBox::down-arrow {{ image: url(CHEVRON_ASSET); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {popup}; color: {text}; selection-background-color: {popupSel}; selection-color: {accentText}; border: 1px solid {popupLine}; }}
QTextEdit, QPlainTextEdit {{ background: {surface}; border: 1px solid {surfaceLine}; border-radius: 7px; padding: 10px; selection-background-color: {textSel}; }}
QTableWidget {{ background: {surface}; alternate-background-color: {surfaceAlt}; border: 1px solid {surfaceLine}; border-radius: 7px; gridline-color: {grid}; selection-background-color: {rowSel}; selection-color: {rowSelText}; }}
QTableWidget::item {{ padding: 7px; border-bottom: 1px solid {grid}; }}
QTableWidget::item:selected {{ background: {rowSel}; color: {rowSelText}; }}
QHeaderView {{ background: {popup}; }}
QHeaderView::section {{ background: {popup}; color: {headText}; padding: 10px 8px; border: none; border-bottom: 1px solid {field_line}; font-size: 11px; font-weight: 600; }}
QTableCornerButton::section {{ background: {popup}; border: none; }}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator, QTableWidget::indicator {{ width: 16px; height: 16px; border: 1px solid {checkLine}; border-radius: 3px; background: {field}; }}
QCheckBox::indicator:checked, QTableWidget::indicator:checked {{ background: {accent}; border-color: {checkOnLine}; image: url(CHECK_ASSET); }}
QCheckBox:focus {{ color: {accentText}; }}
QScrollBar:vertical {{ background: {scrollTrack}; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {scrollHandle}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: {scrollTrack}; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {scrollHandle}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QSplitter::handle {{ background: {surfaceLine}; width: 1px; margin: 0 5px; }}
QStatusBar {{ background: {sidebar}; color: {headText}; border-top: 1px solid {surfaceLine}; padding: 4px 12px; }}
QStatusBar::item {{ border: none; }}
QLabel#muted {{ color: {muted}; }}
QLabel#warning {{ color: {warn}; }}
QLabel#emptyState {{ color: {empty}; background: transparent; font-size: 13px; padding: 12px; }}
QLabel#panelTitle {{ color: {textStrong}; font-size: 16px; font-weight: 600; }}
QWidget#brandBlock {{ background: transparent; }}
QLabel#sectionTitle {{ color: {eyebrow}; font-size: 11px; font-weight: 600; letter-spacing: 1px; padding: 14px 0 4px 0; border-bottom: 1px solid {line}; margin-bottom: 6px; }}
QLabel#statusOk {{ color: {ok}; font-weight: 600; }}
QLabel#statusWarn {{ color: {warn}; }}
QLabel#statusError {{ color: {error}; }}
QToolTip {{ color: {tipText}; background: {tipBg}; border: 1px solid {tipLine}; padding: 6px; }}
"""

# Two palettes with the same keys. Dark is the original graphite/copper look; light is its daylight pair
# (warm paper, darker copper so text and the accent keep at least 4.5:1 contrast on white).
DARK = {
    "ok": "#4ade80",
    "error": "#f87171",
    "bg": "#171b20",
    "text": "#ece9e2",
    "sidebar": "#101318",
    "line": "#2c323b",
    "textStrong": "#f2ede5",
    "textFaint": "#8e98a6",
    "eyebrow": "#a2acba",
    "title": "#f5f0e8",
    "muted": "#a7b1bf",
    "chipText": "#ddbc96",
    "chipBg": "#292621",
    "chipLine": "#544434",
    "navText": "#aab4c2",
    "navHover": "#1b222b",
    "navHoverText": "#f1ede6",
    "navSel": "#2a2a29",
    "accentText": "#f0c799",
    "accentLine": "#d8a66d",
    "btn": "#242c36",
    "btnText": "#e5e9ef",
    "field_line": "#3b4654",
    "btnHover": "#303b48",
    "btnHoverLine": "#7b899a",
    "btnPressed": "#171e27",
    "btnDisabled": "#20262e",
    "disabledText": "#89929e",
    "disabledLine": "#303844",
    "accent": "#d6aa78",
    "accentHover": "#e9bd8b",
    "accentPressed": "#bd905f",
    "primaryDisabled": "#34322f",
    "primaryDisabledText": "#a59e94",
    "primaryDisabledLine": "#48423c",
    "gearText": "#b9c2ce",
    "field": "#10151b",
    "popup": "#202731",
    "popupSel": "#3c3933",
    "popupLine": "#56616f",
    "surface": "#12171d",
    "surfaceLine": "#303a46",
    "textSel": "#594b3a",
    "surfaceAlt": "#181f27",
    "grid": "#242e3b",
    "rowSel": "#3a352e",
    "rowSelText": "#fff4e4",
    "headText": "#aeb9c8",
    "checkLine": "#8491a2",
    "checkOnLine": "#edc594",
    "scrollTrack": "#151a21",
    "scrollHandle": "#465362",
    "warn": "#e4bc89",
    "empty": "#9ca9ba",
    "tipText": "#f3eadf",
    "tipBg": "#29323d",
    "tipLine": "#657181",
}

LIGHT = {
    "ok": "#1a7f37",
    "error": "#b42318",
    "bg": "#f6f5f2",
    "text": "#1f2328",
    "sidebar": "#eceae5",
    "line": "#d9d6cf",
    "textStrong": "#16191d",
    "textFaint": "#69707a",
    "eyebrow": "#5f6670",
    "title": "#16191d",
    "muted": "#5c636d",
    "chipText": "#7a4f1e",
    "chipBg": "#f3e7d7",
    "chipLine": "#ddc3a1",
    "navText": "#3f454d",
    "navHover": "#e2dfd8",
    "navHoverText": "#16191d",
    "navSel": "#e6dccd",
    "accentText": "#7a4f1e",
    "accentLine": "#a86f2e",
    "btn": "#ffffff",
    "btnText": "#1f2328",
    "field_line": "#c9c5bd",
    "btnHover": "#f1efea",
    "btnHoverLine": "#9a958c",
    "btnPressed": "#e6e3dc",
    "btnDisabled": "#f1f0ec",
    "disabledText": "#9a9ea5",
    "disabledLine": "#dedbd5",
    "accent": "#a86f2e",
    "accentHover": "#95601f",
    "accentPressed": "#7f5119",
    "primaryDisabled": "#ebe3d7",
    "primaryDisabledText": "#a39784",
    "primaryDisabledLine": "#dccfbc",
    "gearText": "#3f454d",
    "field": "#ffffff",
    "popup": "#ffffff",
    "popupSel": "#efe4d4",
    "popupLine": "#c9c5bd",
    "surface": "#ffffff",
    "surfaceLine": "#dad6ce",
    "textSel": "#ecd9bf",
    "surfaceAlt": "#faf9f6",
    "grid": "#ebe8e2",
    "rowSel": "#efe1cd",
    "rowSelText": "#16191d",
    "headText": "#5c636d",
    "checkLine": "#8e939a",
    "checkOnLine": "#a86f2e",
    "scrollTrack": "#efede8",
    "scrollHandle": "#c4c0b8",
    "warn": "#8a5a17",
    "empty": "#6b727c",
    "tipText": "#1f2328",
    "tipBg": "#ffffff",
    "tipLine": "#c9c5bd",
}

_assets = Path(__file__).with_name("assets")


def stylesheet(scheme: str = "dark") -> str:
    palette = LIGHT if scheme == "light" else DARK
    css = _TEMPLATE.format(**palette)
    suffix = "-light" if scheme == "light" else ""
    return (css.replace("CHEVRON_ASSET", (_assets / f"chevron{suffix}.svg").as_posix())
               .replace("CHECK_ASSET", (_assets / f"check{suffix}.svg").as_posix())
               .replace("UP_ASSET", (_assets / f"chevron-up{suffix}.svg").as_posix()))


def system_scheme() -> str:
    """'light' or 'dark', following the operating system (Windows: Settings > Personalization > Colors)."""
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    try:
        if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Light:
            return "light"
    except AttributeError:  # Qt older than 6.5
        pass
    return "dark"


def section_title(text: str) -> QLabel:
    """A small uppercase-style heading with a rule under it, used to group a page into sections."""
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def set_status(label, kind: str) -> None:
    """kind: 'ok', 'warn' or 'error'. Colours come from the active theme."""
    label.setObjectName({"ok": "statusOk", "warn": "statusWarn"}.get(kind, "statusError"))
    label.style().unpolish(label)
    label.style().polish(label)


def accent(scheme: str) -> str:
    return (LIGHT if scheme == "light" else DARK)["accent"]


STYLESHEET = stylesheet("dark")  # kept for callers that want the classic look

PAGE_INFO = (
    ("Discover models", "Find a model. Choose its files. Preserve a precise revision."),
    ("Download queue", "Every file in order. Pause and resume without losing progress."),
    ("Your archive library", "Completed models, documentation, and disc history in one place."),
    ("Build an archive", "Assemble your vault items, then burn a disc or export an ISO."),
    ("Runtime collection", "Keep the tools your models need alongside the archive."),
    ("Workspace settings", "Storage locations, burn defaults, credentials, and branding."),
)

def nav_icon(index: int, scheme: str = "dark") -> QIcon:
    """Small original vector marks rendered at 2x for high DPI screens."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(accent(scheme)), 1.5))
    if index == 0:
        painter.drawEllipse(3, 3, 10, 10)
        painter.drawLine(12, 12, 17, 17)
    elif index == 1:
        for y in (5, 10, 15):
            painter.drawLine(7, y, 17, y)
            painter.drawPoint(3, y)
    elif index == 2:
        painter.drawRoundedRect(3, 3, 14, 14, 2, 2)
        painter.drawLine(3, 8, 17, 8)
        painter.drawLine(8, 12, 12, 12)
    elif index == 3:
        painter.drawEllipse(2, 2, 16, 16)
        painter.drawEllipse(8, 8, 4, 4)
        painter.drawLine(10, 2, 10, 6)
    else:
        painter.drawRoundedRect(2, 4, 16, 12, 2, 2)
        painter.drawLine(6, 8, 9, 10)
        painter.drawLine(9, 10, 6, 12)
        painter.drawLine(11, 12, 14, 12)
    painter.end()
    return QIcon(pixmap)

class EmptyState(QObject):
    """An empty table remains readable and explains the next useful action."""
    def __init__(self, table: QTableWidget, text: str):
        super().__init__(table)
        self.table = table
        self.label = QLabel(text, table.viewport())
        self.label.setObjectName("emptyState")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        table.viewport().installEventFilter(self)
        for signal in (table.model().rowsInserted, table.model().rowsRemoved, table.model().modelReset):
            signal.connect(self.update)
        self.update()

    def update(self, *args):
        if not isValid(self.table) or not isValid(self.label):
            return
        self.label.setGeometry(self.table.viewport().rect())
        self.label.setVisible(self.table.rowCount() == 0)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            self.update()
        return False

def polish_tables(page, hints: dict[str, str]):
    for table in page.findChildren(QTableWidget):
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(38)
        table.horizontalHeader().setMinimumSectionSize(64)
        table.horizontalHeader().setStretchLastSection(True)
    if hasattr(page, 'packs'):
        for index, width in enumerate((76, 250, 110, 110)):
            page.table.setColumnWidth(index, width)
    if hasattr(page, 'results'):
        header = page.files.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        page.files.setColumnWidth(2, 110)
    page._empty_states = [EmptyState(getattr(page, name), text) for name, text in hints.items()]

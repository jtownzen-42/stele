"""Stele's graphite / copper desktop design system. Presentation only."""
from pathlib import Path
from PySide6.QtCore import QEvent, QObject, Qt
from shiboken6 import isValid
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget

STYLESHEET = """
QMainWindow, QWidget { background: #171b20; color: #ece9e2; font-family: "Segoe UI"; font-size: 13px; }
QWidget#sidebar { background: #101318; border-right: 1px solid #2c323b; }
QLabel { background: transparent; }
QLabel#brand { color: #f2ede5; font-size: 22px; font-weight: 700; letter-spacing: 3px; }
QLabel#brandNote { color: #8e98a6; font-size: 11px; }
QLabel#eyebrow { color: #a2acba; font-size: 10px; font-weight: 600; letter-spacing: 2px; }
QLabel#pageTitle { color: #f5f0e8; font-size: 28px; font-weight: 600; }
QLabel#pageSubtitle { color: #a7b1bf; font-size: 13px; }
QWidget#pageHeader { border-bottom: 1px solid #2c323b; }
QLabel#edition { color: #ddbc96; background: #292621; border: 1px solid #544434; border-radius: 6px; padding: 6px 12px; font-size: 11px; }
QListWidget#nav { background: transparent; border: none; outline: none; padding: 4px 12px; }
QListWidget#nav::item { color: #aab4c2; padding: 13px 14px; margin: 3px 0; border-radius: 7px; }
QListWidget#nav::item:hover { background: #1b222b; color: #f1ede6; }
QListWidget#nav::item:selected { background: #2a2a29; color: #f0c799; border-left: 3px solid #d8a66d; }
QPushButton { background: #242c36; color: #e5e9ef; border: 1px solid #3b4654; border-radius: 6px; padding: 8px 14px; font-weight: 500; }
QPushButton:hover { background: #303b48; border-color: #7b899a; }
QPushButton:pressed { background: #171e27; }
QPushButton:focus { border: 2px solid #d8a66d; }
QPushButton:disabled { background: #20262e; color: #89929e; border-color: #303844; }
QPushButton#primary { background: #d6aa78; color: #171b20; border-color: #d6aa78; font-weight: 600; }
QPushButton#primary:hover { background: #e9bd8b; border-color: #e9bd8b; }
QPushButton#primary:pressed { background: #bd905f; }
QPushButton#primary:disabled { background: #34322f; color: #a59e94; border-color: #48423c; }
QPushButton#gear { background: transparent; color: #b9c2ce; text-align: left; border-color: #303844; margin: 12px; }
QLineEdit, QComboBox, QSpinBox { background: #10151b; border: 1px solid #3b4654; border-radius: 5px; padding: 8px 10px; min-height: 18px; selection-background-color: #d6aa78; selection-color: #171b20; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #d8a66d; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url(CHEVRON_ASSET); width: 12px; height: 12px; }
QSpinBox::up-button, QSpinBox::down-button { width: 24px; border-left: 1px solid #3b4654; }
QSpinBox::up-arrow { image: url(UP_ASSET); width: 12px; height: 12px; }
QSpinBox::down-arrow { image: url(CHEVRON_ASSET); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: #202731; color: #ece9e2; selection-background-color: #3c3933; selection-color: #f0c799; border: 1px solid #56616f; }
QTextEdit, QPlainTextEdit { background: #12171d; border: 1px solid #303a46; border-radius: 7px; padding: 10px; selection-background-color: #594b3a; }
QTableWidget { background: #12171d; alternate-background-color: #181f27; border: 1px solid #303a46; border-radius: 7px; gridline-color: #242e3b; selection-background-color: #3a352e; selection-color: #fff4e4; }
QTableWidget::item { padding: 7px; border-bottom: 1px solid #242e3b; }
QTableWidget::item:selected { background: #3a352e; color: #fff4e4; }
QHeaderView { background: #202731; }
QHeaderView::section { background: #202731; color: #aeb9c8; padding: 10px 8px; border: none; border-bottom: 1px solid #3b4654; font-size: 11px; font-weight: 600; }
QTableCornerButton::section { background: #202731; border: none; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator, QTableWidget::indicator { width: 16px; height: 16px; border: 1px solid #8491a2; border-radius: 3px; background: #10151b; }
QCheckBox::indicator:checked, QTableWidget::indicator:checked { background: #d6aa78; border-color: #edc594; image: url(CHECK_ASSET); }
QCheckBox:focus { color: #f0c799; }
QScrollBar:vertical { background: #151a21; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #465362; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: #151a21; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #465362; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QSplitter::handle { background: #303a46; width: 1px; margin: 0 5px; }
QStatusBar { background: #101318; color: #aeb9c8; border-top: 1px solid #303a46; padding: 4px 12px; }
QStatusBar::item { border: none; }
QLabel#muted { color: #a7b1bf; }
QLabel#warning { color: #e4bc89; }
QLabel#emptyState { color: #9ca9ba; background: transparent; font-size: 13px; padding: 12px; }
QToolTip { color: #f3eadf; background: #29323d; border: 1px solid #657181; padding: 6px; }
"""
_assets = Path(__file__).with_name("assets")
STYLESHEET = STYLESHEET.replace("CHEVRON_ASSET", (_assets / "chevron.svg").as_posix()).replace("CHECK_ASSET", (_assets / "check.svg").as_posix()).replace("UP_ASSET", (_assets / "chevron-up.svg").as_posix())

PAGE_INFO = (
    ("Discover models", "Find a model. Choose its files. Preserve a precise revision."),
    ("Download queue", "Every file in order. Pause and resume without losing progress."),
    ("Your archive library", "Completed models, documentation, and disc history in one place."),
    ("Build an archive", "Assemble your vault items, then burn a disc or export an ISO."),
    ("Runtime collection", "Keep the tools your models need alongside the archive."),
    ("Workspace settings", "Storage locations, burn defaults, credentials, and branding."),
)

def nav_icon(index: int) -> QIcon:
    """Small original vector marks rendered at 2x for high DPI screens."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#d6aa78"), 1.5))
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

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui_common.dashboard import load_dashboard


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " Kč"


class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Multi-Finance")
        self.resize(1280, 780)
        self._build_ui()

    def _build_ui(self) -> None:
        data = load_dashboard()
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 26, 18, 26)
        brand = QLabel("MF  Multi-Finance")
        brand.setObjectName("brand")
        side.addWidget(brand)
        side.addSpacing(40)
        for label in ("Přehled", "Účetní deník", "Faktury", "Výkazy", "Nastavení"):
            button = QPushButton(label)
            button.setObjectName("navActive" if label == "Přehled" else "nav")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            side.addWidget(button)
        side.addStretch()
        side.addWidget(QLabel("Firma · klient #1"))
        layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(42, 38, 42, 38)
        title = QLabel("Dobré ráno")
        title.setObjectName("title")
        subtitle = QLabel(f"Přehled účetnictví za {data['period']}")
        subtitle.setObjectName("muted")
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        if not data["available"]:
            notice = QLabel("Režim náhledu — " + data["message"])
            notice.setObjectName("notice")
            notice.setWordWrap(True)
            content_layout.addWidget(notice)

        cards = QGridLayout()
        labels = (("Hrubý pracovní kapitál", "gross_wc"), ("Čistý pracovní kapitál", "net_wc"), ("Likvidní kapitál", "liquid_wc"))
        for column, (label, key) in enumerate(labels):
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(label))
            value = QLabel(money(data["metrics"][key]))
            value.setObjectName("cardValue")
            card_layout.addWidget(value)
            cards.addWidget(card, 0, column)
        content_layout.addLayout(cards)

        table_title = QLabel("Pohledávky a závazky")
        table_title.setObjectName("sectionTitle")
        content_layout.addWidget(table_title)
        table = QTableWidget(len(data["invoices"]), 4)
        table.setHorizontalHeaderLabels(["Partner", "Typ", "Splatnost", "Částka"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row_index, item in enumerate(data["invoices"]):
            values = (item["partner"], item["kind"], item["due_date"], f"{item['amount']:,.2f}".replace(",", " ") + " Kč")
            for column, value in enumerate(values):
                table.setItem(row_index, column, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        content_layout.addWidget(table, 1)
        layout.addWidget(content, 1)
        self.setStyleSheet(STYLESHEET)


STYLESHEET = """
#root { background: #f6f8fc; color: #172033; font-family: 'Segoe UI'; }
#sidebar { background: #101a35; color: #c9d1e6; }
#brand { color: white; font-size: 18px; font-weight: 700; }
#nav, #navActive { border: 0; border-radius: 8px; padding: 11px; text-align: left; color: #aeb9d2; background: transparent; }
#navActive, #nav:hover { background: #23305a; color: white; }
#title { font-size: 30px; font-weight: 700; }
#muted { color: #667085; margin-bottom: 18px; }
#notice { background: #fff8e8; border: 1px solid #f0c36b; border-radius: 8px; color: #71521b; padding: 11px; margin-bottom: 14px; }
#card { background: white; border: 1px solid #e8ecf3; border-radius: 12px; padding: 10px; }
#cardValue { font-size: 23px; font-weight: 700; }
#sectionTitle { font-size: 16px; font-weight: 700; margin-top: 22px; margin-bottom: 8px; }
QTableWidget { background: white; border: 1px solid #e8ecf3; border-radius: 10px; gridline-color: #e8ecf3; }
QHeaderView::section { background: white; color: #667085; border: 0; border-bottom: 1px solid #e8ecf3; font-weight: 600; padding: 10px; }
"""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())

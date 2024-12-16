import json
import re
import sys
from queue import Queue
from time import sleep

from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
                             QWidget, QScrollArea, QTextEdit, QLabel, QPushButton, QFileDialog, QSplitter, QTreeWidget,
                             QTreeWidgetItem)
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread

from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from executor import Executor


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("blue"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [r"\bin\b",
            r"\bdef\b", r"\bclass\b", r"\bimport\b", r"\bfrom\b", r"\breturn\b",
            r"\bif\b", r"\belif\b", r"\belse\b", r"\bwhile\b", r"\bfor\b", r"\btry\b", r"\bexcept\b",
            r"\bwith\b", r"\bas\b", r"\bpass\b", r"\bbreak\b", r"\bcontinue\b", r"\blambda\b"
        ]
        for keyword in keywords:
            self.highlighting_rules.append((re.compile(keyword), keyword_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("magenta"))
        self.highlighting_rules.append((re.compile(r"\".*?\"|'.*?'"), string_format))

        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("green"))
        self.highlighting_rules.append((re.compile(r"#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, char_format in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, char_format)

class Cell(QTextEdit):
    run = pyqtSignal(object)
    def run_clicked(self):
        self.run.emit(self)

    def keyPressEvent(self, e, QKeyEvent=None):
        QTextEdit.keyPressEvent(self, e)
        self.setMinimumHeight(int(self.document().size().height()+10))

    def resizeEvent(self, a0, QResizeEvent=None):
        super().resizeEvent(a0)
        self.setMinimumHeight(int(self.document().size().height()+10))


class Code(Cell):
    def __init__(self):
        super().__init__()
        self.setFont(QFont("Monospace", 10))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.syntax_highlighter = PythonSyntaxHighlighter(self.document())
        self.button = QPushButton("▶", self)
        self.button.setFixedSize(25, 25)
        self.button.clicked.connect(self.run_clicked)

    def resizeEvent(self, a0, QResizeEvent=None):
        super().resizeEvent(a0)
        self.button.setGeometry(self.width() - self.button.width(), self.height() - self.button.height(),
                                self.button.width(), self.button.height())

    def keyPressEvent(self, event):
        if event == QKeySequence.Paste:  # Intercept the paste shortcut
            clipboard = QApplication.clipboard()
            plain_text = clipboard.text()  # Get only the plain text
            self.insertPlainText(plain_text)  # Insert plain text only
            self.setMinimumHeight(int(self.document().size().height()+10))
        elif event.key() == Qt.Key_Tab:  # Check if the Tab key is pressed
            self.insertPlainText("    ")  # Insert four spaces
        elif event.key() == Qt.Key_Return:  # Check if the Enter key is pressed
            if self.toPlainText().strip().endswith(":"):
                super().keyPressEvent(event)
                self.insertPlainText("    ")
            elif self.textCursor().block().text().startswith("    "):
                super().keyPressEvent(event)
                self.insertPlainText("    ")
            else:
                super().keyPressEvent(event)
        elif event.key() == Qt.Key_Backspace:  # Check if the Backspace key is pressed
            if self.textCursor().block().text()=="    ":
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                cursor.removeSelectedText()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class Markdown(Cell):
    def __init__(self):
        super().__init__()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QTextEdit {
                border: none;
                background: transparent;
            }
        """)
        self.setReadOnly(True)


class MainWindow(QMainWindow):

    def open(self, name):
        if name is None:
            dialog = QFileDialog(self)
            dialog.setFileMode(QFileDialog.AnyFile)
            dialog.setNameFilter("Text files (*.ipynb)")
            dialog.setViewMode(QFileDialog.Detail)
            if dialog.exec_():
                name = dialog.selectedFiles()[0]
            else:
                return

        with open(name, "r") as f:
            json_data = json.load(f)
            for ws in json_data["worksheets"]:
                for cell in ws["cells"]:
                    if cell["cell_type"] == "code":
                        edit = Code()
                        source = cell["input"]
                        text = str()
                        for line in source:
                            text += line
                        edit.setPlainText(text)
                    elif cell["cell_type"] == "markdown":
                        edit = Markdown()
                        text = str()
                        source = cell["source"]
                        for line in source:
                            text += line
                        edit.setMarkdown(text)
                    edit.run.connect(self.run_cell)
                    self.edits.append(edit)
                    self.helper_layout.addWidget(self.edits[-1])

    def run_cell(self, edit):
        self.queue.put(edit.toPlainText())
        #self.execute_cell(edit.toPlainText())


    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Scroll Areas Layout")
        self.resize(1000, 800)

        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        m_open = self.file_menu.addAction("Open")
        m_open.triggered.connect(self.open)


        # Create a central widget and main layout
        splitter = QSplitter()
        #main_layout = QHBoxLayout(central_widget)

        # Create first scroll area with fixed max height
        scroll_area1 = QScrollArea()

        text_edit1 = QTextEdit()
        helper = QWidget()
        self.helper_layout = QVBoxLayout(helper)
        helper.setLayout(self.helper_layout)
        self.play = QPushButton("Play")
        self.helper_layout.addWidget(self.play)
        self.tree = QTreeWidget()

        self.helper_layout.addWidget(self.tree)
        self.edits = []
        # for i in range(10):
        #     self.edits.append(QTextEdit())
        #     helper_layout.addWidget(self.edits[-1])
        # helper_layout.setAlignment(Qt.AlignTop)
        # self.edits[0].setPlainText("a=4\nb=6\n")

        scroll_area1.setWidget(helper)
        scroll_area1.setWidgetResizable(True)
        #scroll_area1.setMaximumHeight(200)

        self.play.clicked.connect(self.clicked)

        # Add widgets to main layout
        #main_layout.setAlignment(Qt.AlignTop)
        splitter.addWidget(scroll_area1)

        self.jupyter_widget = RichJupyterWidget()
        self.jupyter_widget.kernel_manager = QtInProcessKernelManager()
        self.jupyter_widget.kernel_manager.start_kernel()
        self.jupyter_widget.kernel_client = self.jupyter_widget.kernel_manager.client()
        self.jupyter_widget.kernel_client.start_channels()

        splitter.addWidget(self.jupyter_widget)
        self.setCentralWidget(splitter)

        self.queue = Queue()
        self.executor = Executor(self.queue, self.jupyter_widget)
        self.executor.run_code.connect(self.execute)
        self.executor.start()

        self.open("example.ipynb")

        QApplication.processEvents()
        splitter.setSizes([800, 800])


    def clicked(self):
        for edit in [e for e in self.edits if isinstance(e, Code)]:
            self.queue.put(edit.toPlainText())

    def execute(self, text):
        self.jupyter_widget.execute(text, interactive=False)
        return


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
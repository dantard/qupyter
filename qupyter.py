import json
import random
import re
import sys
from queue import Queue
from time import sleep
import yaml
from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QKeySequence, QTextCursor, QPalette, \
    QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
                             QWidget, QScrollArea, QTextEdit, QLabel, QPushButton, QFileDialog, QSplitter, QTreeWidget,
                             QTreeWidgetItem, QCheckBox, QLineEdit)
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
        self.setMinimumHeight(int(self.document().size().height() + 10))

    def resizeEvent(self, a0, QResizeEvent=None):
        super().resizeEvent(a0)
        self.setMinimumHeight(int(self.document().size().height() + 10))

class InputBox(QWidget):
    def __init__(self, data, index):
        super().__init__()
        self.data = data
        self.index = index
        self.type = self.data.get("value", "int")
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(QLabel(self.data.get("description", "Input")))
        self.input = QLineEdit()
        self.input.setText(str(self.data.get("default", "")).strip())
        if self.type == "int":
            self.input.setValidator(QIntValidator())
        elif self.type == "float":
            self.input.setValidator(QDoubleValidator())

        self.layout().addWidget(self.input)

    def set(self, text):
        value = text.pop(0)
        if self.type == "int":
            self.input.setText(str(int(value)))
        elif self.type == "float":
            self.input.setText(str(float(value)))
        else:
            self.input.setText(value)



    def get(self):
        if self.type == "int":
            return int(self.input.text())
        elif self.type == "float":
            return float(self.input.text())
        return self.input.text()
class Multiple(QWidget):

    def __init__(self, data, index):
        super().__init__()
        self.data = data
        self.index = index
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel(str(self.index) + ". " + data["description"]))
        self.cbs = []
        for i, op in enumerate(data["options"]):
            cb = QCheckBox(op)
            cb.index = i
            self.cbs.append(cb)
        shuffled = [c for c in self.cbs]
        #random.shuffle(shuffled)
        for cb in shuffled:
            self.layout().addWidget(cb)
    def get(self):
        return [1 if cb.isChecked() else 0 for cb in self.cbs]

    def set(self, data):
        for cb in self.cbs:
            value = int(data.pop(0))
            cb.setChecked(value>0)

class Code(Cell):
    def __init__(self):
        super().__init__()
        self.setFont(QFont("Monospace", 10))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.syntax_highlighter = PythonSyntaxHighlighter(self.document())
        self.button = QPushButton("▶", self)
        self.button.setFixedSize(20, 20)
        self.button.clicked.connect(self.run_clicked)
        self.update_background_color()
        self.remove_std_out = False

    def update_background_color(self):
        if self.isReadOnly():
            light_red = QColor(255, 0, 0, 10)  # RGBA: Red, Green, Blue, Alpha
        else:
            light_red = QColor(0, 255, 0, 10)  # RGBA: Red, Green, Blue, Alpha
        palette = self.palette()
        palette.setColor(QPalette.Base, light_red)
        self.setPalette(palette)

    def setReadOnly(self, ro: bool) -> None:
        super().setReadOnly(ro)
        self.update_background_color()

    def resizeEvent(self, a0, QResizeEvent=None):
        super().resizeEvent(a0)
        self.button.setGeometry(self.width() - self.button.width() - 1, self.height() - self.button.height() - 1,
                                self.button.width(), self.button.height())
        self.button.setFlat(True)

    def keyPressEvent(self, event):
        if event == QKeySequence.Paste:  # Intercept the paste shortcut
            clipboard = QApplication.clipboard()
            plain_text = clipboard.text()  # Get only the plain text
            self.insertPlainText(plain_text)  # Insert plain text only
            self.setMinimumHeight(int(self.document().size().height() + 10))
        elif event.key() == Qt.Key_Tab:  # Check if the Tab key is pressed
            self.insertPlainText("    ")  # Insert four spaces
        elif event.key() == Qt.Key_Return:  # Check if the Enter key is pressed
            # Check if CTRL is pressed
            if event.modifiers() == Qt.ControlModifier:
                self.button.click()
            elif self.toPlainText().strip().endswith(":"):
                super().keyPressEvent(event)
                self.insertPlainText("    ")
            elif self.textCursor().block().text().startswith("    "):
                super().keyPressEvent(event)
                self.insertPlainText("    ")
            else:
                super().keyPressEvent(event)
        elif event.key() == Qt.Key_Backspace:  # Check if the Backspace key is pressed
            if self.textCursor().block().text() == "    ":
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
                background: white;
            }
        """)
        self.setReadOnly(True)


class MainWindow(QMainWindow):

    def open_file(self, name=None):
        if name is None:
            name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Jupyter Notebook Files (*.ipynb)")

        with open(name, "r") as f:
            json_data = json.load(f)
            for cell in json_data["cells"]:
                print("aoaoaoao", cell["cell_type"])
                if cell["cell_type"] == "raw":
                    source = cell["source"]
                    source = "".join(source)

                    data = yaml.safe_load(source)
                    if data.get("type", None) == "multiple":
                        edit = Multiple(data, self.index)
                    elif data.get("type", None) == "input":
                        edit = InputBox(data, self.index)
                    else:
                        raise ValueError("Invalid type" + str(data))
                    self.index = self.index + 1
                    self.interactions.append(edit)
                    self.helper_layout.addWidget(edit)

                elif cell["cell_type"] == "code":
                    edit = Code()

                    # Treat Metadata
                    metadata = cell.get("metadata", None)
                    if metadata is not None:
                        editable = metadata.get("editable", True)
                        edit.setReadOnly(not editable)
                        tag_list = metadata.get("tags", [])
                        for tag in tag_list:
                            if tag == "remove-stdout":
                                edit.remove_std_out = True

                    source = cell["source"]
                    text = str()
                    for line in source:
                        text += line
                    edit.setPlainText(text)
                    edit.run.connect(self.run_cell)
                    self.edits.append(edit)
                    self.helper_layout.addWidget(self.edits[-1])

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

    def run_cell(self, edit: Code):
        print("PUTTING")
        self.queue.put((edit.toPlainText(), edit.remove_std_out))
        # self.execute_cell(edit.toPlainText())

    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Scroll Areas Layout")
        self.resize(1000, 800)

        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.file_menu.addAction("Open", self.open_file)
        self.file_menu.addAction("Export", self.export)
        self.file_menu.addAction("Import", self.import_file)

        # Create a central widget and main layout
        splitter = QSplitter()
        # main_layout = QHBoxLayout(central_widget)

        # Create first scroll area with fixed max height
        scroll_area1 = QScrollArea()

        text_edit1 = QTextEdit()
        helper = QWidget()
        self.helper_layout = QVBoxLayout(helper)
        helper.setLayout(self.helper_layout)
        self.play = QPushButton("Run All")
        self.stop_btn = QPushButton("Stop")
        # self.helper_layout.addWidget(self.play)

        self.index = 0
        self.edits = []
        self.interactions = []

        scroll_area1.setWidget(helper)
        scroll_area1.setWidgetResizable(True)
        # scroll_area1.setMaximumHeight(200)

        self.play.clicked.connect(self.clicked)
        self.stop_btn.clicked.connect(self.stop)

        # Add widgets to main layout
        # main_layout.setAlignment(Qt.AlignTop)
        left_outer_helper = QWidget()
        left_outer_layout = QVBoxLayout(left_outer_helper)
        left_outer_layout.addWidget(scroll_area1)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.play)
        buttons_layout.addWidget(self.stop_btn)

        left_outer_layout.addLayout(buttons_layout)
        splitter.addWidget(left_outer_helper)

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

        self.open_file("p2.ipynb")

        QApplication.processEvents()
        splitter.setSizes([800, 800])
    def import_file(self):
        name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "INF Files (*.inf)")
        if name:
            with open(name, "r") as f:
                text = f.read()
                data = text.split(",")
                for e in self.interactions:
                    e.set(data)
    def export(self):
        result = []
        for e in self.interactions:
            if isinstance(e, Multiple):
                result += e.get()
            elif isinstance(e, InputBox):
                result.append(e.get())
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "INF Files (*.inf)")
        if save_path:
            save_path = save_path.replace(".inf", "") + ".inf"
            with open(save_path, "w") as f:
                text = ""
                for elem in result:
                    text += str(elem) + ","
                f.write(text[:-1])



    def clicked(self):
        self.queue.put(("# QP_BEGIN", True))
        for edit in [e for e in self.edits if isinstance(e, Code)]:
            self.queue.put((edit.toPlainText(), edit.remove_std_out))
        self.queue.put(("# QP_END", True))

    def stop(self):
        self.executor.empty_queue(self.queue)

    def execute(self, text, hidden):
        print("text", text, hidden)
        if text == "# QP_BEGIN":
            #self.setEnabled(False)
            pass
        elif text == "# QP_END":
            self.setEnabled(True)
        elif text == "# QP_ERROR":
            self.setEnabled(True)

        self.jupyter_widget.execute(text, interactive=False, hidden=hidden)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

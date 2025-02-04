import time
from queue import Queue
from time import sleep

from PyQt5.QtCore import QThread, pyqtSignal


class Executor(QThread):

    run_code = pyqtSignal(str, bool)

    def __init__(self, queue, jupyter_widget):
        super().__init__()
        self.queue = queue
        self.messages = Queue()
        self.status = "execute"
        self.jupyter_widget = jupyter_widget
        self.jupyter_widget.kernel_client.iopub_channel.message_received.connect(self.handle_message)

    def run(self):
        while True:
            status = self.messages.get()

            if status == "idle":
                item, hidden = self.queue.get()
                self.empty_queue(self.messages)
                self.run_code.emit(item, hidden)
            elif status == "error":
                self.empty_queue(self.queue)
                self.run_code.emit("# QP_ERROR", True)
            elif status == "busy":
                time.sleep(0.01)

    @staticmethod
    def empty_queue(queue):
        while not queue.empty():
            queue.get()

    def handle_message(self, msg):
        #print("msg", msg)
        if msg["msg_type"] in ["error"]:
            print("putting", msg["msg_type"])
            self.messages.put(msg["msg_type"])
        elif msg["msg_type"] == "status":
            print("putting", msg["content"]["execution_state"])
            self.messages.put(msg["content"]["execution_state"])

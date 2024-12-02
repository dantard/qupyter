from queue import Queue
from time import sleep

from PyQt5.QtCore import QThread, pyqtSignal


class Executor(QThread):

    run_code = pyqtSignal(str)

    def __init__(self, queue, jupyter_widget):
        super().__init__()
        self.queue = queue
        self.messages = Queue()
        self.status = "execute"
        self.jupyter_widget = jupyter_widget
        self.jupyter_widget.kernel_client.iopub_channel.message_received.connect(self.handle_message)

    def run(self):
        while True:
            if self.status == "execute":
                item = self.queue.get()
                print("Executing")
                self.empty_queue(self.messages)
                self.run_code.emit(item)
                self.status = "launched"
            elif self.status == "launched":
                print("launched")
                message = self.messages.get()
                print("Got message", message)
                if message == "execute_input":
                    self.status = "waiting_result"
            elif self.status == "waiting_result":
                print("waiting_result")
                message = self.messages.get()
                print("Got message", message)
                if message == "idle":
                    self.status = "execute"
                elif message == "error":
                    self.empty_queue(self.queue)
                    self.status = "execute"

    @staticmethod
    def empty_queue(queue):
        while not queue.empty():
            queue.get()

    def handle_message(self, msg):
        if msg["msg_type"] in ["execute_input","error"]:
            self.messages.put(msg["msg_type"])
        elif msg["msg_type"] == "status":
            self.messages.put(msg["content"]["execution_state"])

# encoding: utf-8

import os
import sys
import pickle
import tempfile

from collections import namedtuple
from datetime import datetime

Request = namedtuple("Request", "action args kwargs")
Result = namedtuple("Result", "success message data")
Report = namedtuple("Report", "type status")
File = namedtuple("File", "path")

CLOSE_SERVER = Request("close", [], {})
CONNECTED = Report("connection", True)

class Remote():
    SOCKET_HOST = "127.0.0.1"
    SOCKET_PORT = 8081
    SSH_HOST = "127.0.0.1"
    SSH_PORT = 22
    BUFSIZE = 1024

    def _print(self, msg, file=sys.stdout):
        now = datetime.now().strftime("%H:%M:%S")
        file.write("[{time}] {msg}\n".format(time=now, msg=msg))
        file.flush()

    def _pack(self, data):
        packet = pickle.dumps(data)
        if sys.getsizeof(packet) > self.BUFSIZE:
            path = os.path.join(tempfile.gettempdir(), "remote_data")
            with open(path, "wb") as file:
                pickle.dump(data, file)
            packet = File(path)

        return packet

class ServerError(Exception):
    pass

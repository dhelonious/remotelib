# encoding: utf-8

import os
import sys
import socket
import pickle
import tempfile

from .remote import Remote, Result, File, CONNECTED, CLOSE_SERVER


class Server(Remote):
    def run(self, logfile="server.log"):
        with open(logfile, "w") as log:
            self._print("Creating socket")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.SOCKET_HOST, self.SOCKET_PORT))
                sock.listen(1)

                connection, address = sock.accept()
                with connection:
                    self._print("Connection established from {}".format(address), file=log)
                    connection.sendall(pickle.dumps(CONNECTED))

                    while True:
                        data = connection.recv(self.BUFSIZE)
                        if data:
                            request = pickle.loads(data)
                            if isinstance(request, File):
                                with open(request.path, "rb") as file:
                                    request = pickle.load(file)
                            self._print("Received {}".format(request), file=log)
                        else:
                            break

                        # Handle closing request
                        if request == CLOSE_SERVER:
                            break

                        try:
                            data = getattr(self, request.action)(*request.args, **request.kwargs)
                            result = Result(True, "", data)
                        except Exception as e:
                            result = Result(False, str(e), None)

                        self._print("Return {}".format(result), file=log)
                        packet = self._pack(result)
                        if isinstance(packet, File):
                            connection.sendall(pickle.dumps(packet))
                        else:
                            connection.sendall(packet)

                self._print("Closing")

    def print(self, msg):
        print(msg, flush=True)

    def _print(self, msg, file=sys.stdout):
        super(Server, self)._print("[Server] {}".format(msg), file=file)

    def tempfile(self, name):
        return os.path.join(tempfile.gettempdir(), name)

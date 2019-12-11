# encoding: utf-8

import os
import sys
import socket
import pickle
import time
import tempfile
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from types import SimpleNamespace

import paramiko
from sshtunnel import open_tunnel
from .remote import Remote, Request, File, CONNECTED, CLOSE_SERVER
from .util import unbuffered


# TODO: Implement ServerProcess class


class Client(Remote):
    logfile = "client.log"

    def __init__(self, host="localhost", user=None, password=None, pkey=None, gateway=None, start_server_cmd=None, timeout=500):

        self.local_mode = (host == "localhost")

        if isinstance(host, str):
            port = self.SOCKET_PORT if self.local_mode else self.SSH_PORT
            self.host = (host, port)
        elif isinstance(host, tuple):
            self.host = host
        else:
            raise ValueError("'host' must be either string or tuple")

        self.user = user
        self.password = password
        self.pkey = pkey

        if isinstance(gateway, str):
            self.gateway = (gateway, self.SSH_PORT)
        elif isinstance(gateway, tuple) or gateway is None:
            self.gateway = gateway
        else:
            raise ValueError("'gateway' must be either string or tuple")

        self.start_server_cmd = start_server_cmd

        self.server = SimpleNamespace(thread=None, stdout=None)
        self.tunnels = None
        self.socket = None
        self.ssh_client = None
        self.ftp_client = None
        self.timeout = timeout

    def __enter__(self):
        if not self.local_mode:
            self._open_tunnels()
            self._open_clients()
        if self.start_server_cmd:
            self._start_server()

        self._connect()
        report = None
        while report != CONNECTED:
            data = self.socket.recv(self.BUFSIZE)
            if data:
                report = pickle.loads(data)

        self._print("Connected to server")

        return self

    def __exit__(self, type_, value, traceback):
        if self.start_server_cmd:
            self._close_server()
        self._disconnect()
        if not self.local_mode:
            self._close_clients()
            self._close_tunnels()

    def _print(self, msg, file=sys.stdout):
        super(Client, self)._print("[Client] {}".format(msg), file=file)

    def __send_request(self, request):
        packet = self._pack(request)
        if isinstance(packet, File):
            packet = pickle.dumps(File(self._remote_path(packet.path)))

        self.socket.sendall(packet)
        return self.socket.recv(self.BUFSIZE)

    def request(self, action, *args, **kwargs):
        request = Request(action, args, kwargs)
        data = self.__send_request(request)
        time.sleep(self.timeout/1000)

        if data:
            result = pickle.loads(data)
            if isinstance(result, File):
                with open(self._local_path(result.path), "rb") as file:
                    result = pickle.load(file)
            # TODO: Improve error handling/printing
            return result
        else:
            return None

    def _local_path(self, remote_path):
        if self.local_mode:
            local_path = remote_path
        else:
            file_name = os.path.basename(remote_path)
            local_path = os.path.join(tempfile.gettempdir(), file_name)
            self.ftp_client.get(remote_path, local_path)

        return local_path

    def _remote_path(self, local_path):
        if self.local_mode:
            remote_path = local_path
        else:
            file_name = os.path.basename(local_path)
            result = self.request("tempfile", file_name)
            if result.success:
                remote_path = result.data
                self.ftp_client.put(local_path, remote_path)
            else:
                raise str(result.message)

        return remote_path

    def __exec_command(self, cmd):
        if self.local_mode:
            # Start server in background
            proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True, universal_newlines=True)
            stdout = unbuffered(proc)
        else:
            # TODO: Check if user and (password or pkey)

            # Execute command in background
            channel = self.ssh_client.get_transport().open_session()
            channel.set_combine_stderr(True)
            channel.get_pty()
            stdout = iter(channel.makefile().readline, b"")
            channel.exec_command(cmd)

        return stdout

    def _start_server(self):
        if not self.start_server_cmd:
            return

        self._print("Starting server")
        self.server.stdout = self.__exec_command(self.start_server_cmd)
        for line in self.server.stdout:
            if line:
                break
            time.sleep(.1)

        self.server.thread = Thread(target=self.__server_output)
        self.server.thread.start()

        # TODO: Raise error on failure

    def __server_output(self):
        for line in self.server.stdout:
            if not self.server.stdout:
                break
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode(sys.stdout.encoding)
            print(line.rstrip(), flush=True)

    def _close_server(self):
        self._print("Closing server")
        self.__send_request(CLOSE_SERVER)
        self.server.thread = None
        self.server.stdout = None

    def _connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(self.host)

    def _disconnect(self):
        if self.socket:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        self.socket = None

    def _open_tunnels(self):
        self.tunnels = {}

        auth = {
            "ssh_username": self.user,
            "ssh_password": self.password,
            "ssh_pkey": self.pkey
        }

        if self.gateway:
            self.tunnels["gateway"] = open_tunnel(
                ssh_address_or_host = self.gateway,
                remote_bind_address = self.host,
                block_on_close=False,
                **auth
            )
            self.tunnels["gateway"].start()
            self.host = ("localhost", self.tunnels["gateway"].local_bind_port)

        self.tunnels["socket"] = open_tunnel(
            ssh_address_or_host = self.host,
            remote_bind_address = (self.SOCKET_HOST, self.SOCKET_PORT),
            block_on_close=False,
            **auth
        )
        self.tunnels["socket"].start()

        self.tunnels["ssh"] = open_tunnel(
            ssh_address_or_host = self.host,
            remote_bind_address = (self.SSH_HOST, self.SSH_PORT),
            block_on_close=False,
            **auth
        )
        self.tunnels["ssh"].start()

        self.host = ("localhost", self.tunnels["socket"].local_bind_port)

    def _close_tunnels(self):
        for tunnel in self.tunnels.values():
            tunnel.close()
        self.tunnels = None

    def _open_clients(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.load_system_host_keys()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        self.ssh_client.connect(
            hostname = "localhost",
            port = self.tunnels["ssh"].local_bind_port,
            username = self.user,
            pkey = paramiko.RSAKey.from_private_key_file(self.pkey)
        )

        self.ftp_client = self.ssh_client.open_sftp()

    def _close_clients(self):
        self.ftp_client.close()
        self.ssh_client.close()

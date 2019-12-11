Small library for writing applications which are partly executed on a server.

Introduction
============

This is a small library to split applications to be partly executed server and client-sided. This is useful if, for example, calculations have to be performed on a specific machine, which only provides access via ssh. With *remotelib* some functions can be executed on the server remotely, while the control remains on the local machine and can be used for interactions and plotting. However, server and client must not be on different machines, so that programs can be used both locally and remotely.

*remotelib* uses a simple server-client architecture. The idea is to write a custom subclass of ``Server``, which contains the functions callable from the ``Client`` instance. Server and client communicate through an ssh tunnel, which also allows for the usage of a gateway (e. g. an access point to another network). Data is pickled and passed either, if small enough, directly by string or via scp.

Example Implementation
======================

Server
------

.. code-block:: python

    #!/usr/bin/env python
    # encoding: utf-8

    import time

    from remotelib.server import Server
    from remotelib.util import progress

    class MyServer(Server):
        def calc(self, a, b, op="+"):
            if op == "+":
                op = lambda a, b: a + b
            elif op == "-":
                op = lambda a, b: a - b
            elif op == "*":
                op = lambda a, b: a * b
            elif op == "/":
                op = lambda a, b: a / b

            return op(a, b)

        def progress(self):
            for i in progress(range(1000), steps=10):
                time.sleep(.005)
            self.print("Finished")

    server = MyServer()
    server.run()

Client
------

.. code-block:: python

    #!/usr/bin/env python
    # encoding: utf-8

    import os
    import platform

    from remotelib.client import Client

    auth = {
        "platform1": {},
        "platform2": {
            "host": "platform1",
            "user": "user",
            "pkey": "/path/to/pkey_file",
        }
    }
    config = {
        "start_server_cmd": "/path/to/server_file",
        **auth[platform.node()]
    }

    with Client(**config) as client:

        result1 = client.request("calc", 4, 1)
        print("The first result ist {}".format(result1.data))

        print("Do something:")
        client.request("progress")

        result2 = client.request("calc", result1.data, 2, op="*")
        print("The second result ist {}".format(result2.data))

# encoding: utf-8

import sys
import time
import contextlib

def unbuffered(proc, stream="stdout"):
    """ Get a Python subprocess' output without buffering

    Normally when you want to get the output of a subprocess in Python you have
    to wait until the process finishes. This is bad for long or indefinitely
    running processes. Here's a way to get the output unbuffered.

    Note: You have to use `universal_newlines=True` in `subprocess.Popen`.

    Source: https://gist.github.com/thelinuxkid/5114777
    """
    stream = getattr(proc, stream)
    with contextlib.closing(stream):
        while True:
            out = []
            last = stream.read(1)
            if not last and proc.poll() is not None:
                break
            while last not in ["\n", "\r\n", "\r"]:
                if not last and proc.poll() is not None:
                    break
                out.append(last)
                last = stream.read(1)
            yield "".join(out)

def fmtduration(duration):
    if not isinstance(duration, float):
        return duration

    if duration <= 60*60: # Minutes and seconds
        return "{:02.0f}:{:02.0f}".format(duration//60, duration%60)
    elif duration <= 24*60*60: # Hours
        return ">{}h".format(duration//(60*60))
    else: # Days
        return ">{}d".format(duration//(24*60*60))

def progress(it, prefix="", file=sys.stdout, steps=1):
    count = len(it)
    step = 0
    start = time.time()
    time_remaining = "?"
    for i, item in enumerate(it):
        yield item

        progress = int(100*i/(count-1))
        if progress >= step:
            step += steps
            now = time.time()
            time_elapsed = now - start
            if i > 0:
                time_remaining = ((count-1) - i)*time_elapsed/i
            file.write("{}{}% {}/{} [{}<{}]\n".format(
                prefix, progress, i+1, count,
                fmtduration(time_elapsed), fmtduration(time_remaining)
            ))
            file.flush()

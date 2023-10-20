import os
import pty
import tty
import termios
import pathlib
import threading
import logging
import fdBus

class PtyBus:
    def __init__(self, nodes, name=None, one_way=False):
        self.log = logging.getLogger(self.__class__.__name__)
        self.n = nodes
        self.name = name

        self.log.info(f"Initializing {self.name}")

        self.pairs = PtyBus.create_pty_pairs(self.n)
        for p in self.pairs:
            self.log.debug(
                f"mfd={p['mfd']} (inh={os.get_inheritable(p['mfd'])}), sfd={p['sfd']}, spath={p['spath']}"
            )
        master_fds = [d["mfd"] for d in self.pairs]
        self.busobj = fdBus.FdBus(master_fds, one_way=False, name=name)

    @staticmethod
    def create_pty_pairs(n):
        ret = []
        for i in range(n):
            d = PtyBus.create_pty_pair()
            ret.append(d)

        return ret

    @staticmethod
    def create_pty_pair():
        master, slave = pty.openpty()
        tty.setraw(master, termios.TCSANOW)
        os.set_inheritable(master, True)

        d = {}
        d["mfd"] = master
        d["sfd"] = slave
        d["spath"] = pathlib.Path(os.ttyname(slave))

        return d

    def start(self):
        self.busobj.start()

    def stop(self):
        self.busobj.stop()
        for p in self.pairs:
            self.log.debug(f"Deleting mfd={p['mfd']}, sfd={p['sfd']}")
            os.close(p["mfd"])
            os.close(p["sfd"])

import os, pty, tty, termios, pathlib, threading
import logging
import fdBus

log = logging.getLogger(__name__)


def delete_pty_pair(pair):
    log.debug(f"Deleting mfd={pair['mfd']}, sfd={pair['sfd']}")
    os.close(pair["mfd"])
    os.close(pair["sfd"])


def delete_pty_pairs(pairs):
    for p in pairs:
        delete_pty_pair(p)


def create_pty_pair():
    master, slave = pty.openpty()
    tty.setraw(master, termios.TCSANOW)
    os.set_inheritable(master, True)

    d = {}
    d["mfd"] = master
    d["sfd"] = slave
    d["spath"] = pathlib.Path(os.ttyname(slave))
    return d


def create_pty_pairs(n):
    ret = []
    for i in range(n):
        d = create_pty_pair()
        ret.append(d)

    return ret


def create_bus(n=0):
    pairs = create_pty_pairs(n)
    master_fds = []
    for pair in pairs:
        log.debug(
            f"mfd={pair['mfd']} (inh={os.get_inheritable(pair['mfd'])}), sfd={pair['sfd']}, spath={pair['spath']}"
        )
        master_fds.append(pair["mfd"])

    log.debug(f"Starting thread with args: {[master_fds]}")
    thread = threading.Thread(target=fdBus.entry, args=[master_fds])
    thread.start()

    return {"pairs": pairs, "thread": thread}

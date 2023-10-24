import logging
import os
import select
import threading


class FdBus:
    def __init__(self, fds, one_way=False, name=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.run_token = False
        self.threads = []
        self.name = name

        self.log.info(f"Initializing {name}")
        if not one_way:
            for i, mfd in enumerate(fds):
                other_master_fds = fds[:i] + fds[i + 1 :]
                thread = threading.Thread(
                    target=self.forward_data, args=[mfd, other_master_fds]
                )
                thread.name = f"{self.__class__.__name__}::{self.name}::mfd-{mfd}"
                self.threads.append(thread)
        else:
            thread = threading.Thread(target=self.forward_data, args=[fds[0], fds[1:]])
            thread.name = f"{self.__class__.__name__}::{self.name}::mfd-{fds[0]}"
            self.threads.append(thread)

    def forward_data(self, reader, writers):
        self.log.debug(f"Starting forward_data on {self.__class__.__name__}, r/w {[reader, writers]}")
        while self.run_token:
            rdy, _, _ = select.select([reader], [], [], 0.5)
            try:
                data = os.read(rdy[0], 1)
            except IndexError:
                continue
            if data:
                for w in writers:
                    os.write(w, data)
        self.log.debug(f"END forward_data on {self.__class__.__name__}, r/w {[reader, writers]}")

    def start(self):
        self.log.info(f"Starting threads {[t.name for t in self.threads]}")
        self.run_token = True
        for t in self.threads:
            t.start()

    def stop(self):
        self.log.info(f"Stopping threads {[t.name for t in self.threads]}")
        self.run_token = False
        for t in self.threads:
            while True:
                try:
                    t.join()
                except KeyboardInterrupt:
                    continue
                else:
                    break


if __name__ == "__main__":
    import ptyBus
    import sys
    import time

    log = logging.getLogger(__name__)
    logging.basicConfig(level="INFO")

    n = 2
    if len(sys.argv) < 3:
        print(f"Creating {n} pty pairs")
        pairs = ptyBus.PtyBus.create_pty_pairs(n)
        master_fds = [i["mfd"] for i in pairs]
        slave_fds = [i["sfd"] for i in pairs]
        slave_paths = [i["spath"] for i in pairs]
        for i in range(n):
            print(
                f"mfd={master_fds[i]} (inh={os.get_inheritable(master_fds[i])}), sfd={slave_fds[i]}, spath={slave_paths[i]}"
            )
    else:
        master_fds = [int(i) for i in sys.argv[1:]]

    bus = FdBus(master_fds, name="busName")
    bus.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down ...")

    bus.stop()

import os, asyncio


def forward_data(reader, writers):
    data = os.read(reader, 1024)
    if data:
        for w in writers:
            os.write(w, data)


def entry(fds, one_way=False):
    loop = asyncio.new_event_loop()

    if not one_way:
        for i, mfd in enumerate(fds):
            other_master_fds = fds[:i] + fds[i + 1 :]
            loop.add_reader(mfd, forward_data, mfd, other_master_fds)
    else:
        loop.add_reader(fds[0], forward_data, fds[0], fds[1:])

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.remove_reader(forward_data)
        loop.stop()
        loop.run_until_complete()


if __name__ == "__main__":
    from ptyBus import create_pty_pairs
    import sys, os, threading

    n = 2
    if len(sys.argv) < 3:
        print(f"Creating {n} pty pairs")
        slave_fds, slave_paths, master_fds, master_paths = create_pty_pairs(n)
        for i in range(n):
            print(
                f"mfd={master_fds[i]} (inh={os.get_inheritable(master_fds[i])}), sfd={slave_fds[i]}, spath={slave_paths[i]}, mpath={master_paths[i]}"
            )
    else:
        master_fds = [int(i) for i in sys.argv[1:]]

    thread = threading.Thread(target=entry, args=[master_fds])
    thread.start()

    try:
        thread.join()
    except KeyboardInterrupt:
        pass

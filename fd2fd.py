import os, asyncio
import threading as thd


def forward_data(reader, writer):
    data = os.read(reader, 1024)
    if data:
        os.write(writer, data)


def entry(fds):
    loop = asyncio.new_event_loop()
    loop.add_reader(fds[0], forward_data, fds[0], fds[1])

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.remove_reader(forward_data)
        loop.stop()
        loop.run_until_complete()

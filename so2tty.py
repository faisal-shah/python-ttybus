#!/usr/bin/env python3

import os
import socket
import threading
import logging
import select

log = logging.getLogger(__name__)


run_token = False


def toSocket(tty, sock):
    global run_token
    try:
        while run_token:
            rdy, _, _ = select.select([tty], [], [], 1)
            try:
                data = os.read(rdy[0], 1)
            except IndexError:
                log.debug("Timed out on tty")
                continue
            if data:
                log.debug(f"toSock: {data}")
                sock.send(data)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except Exception:
        run_token = False
        log.exception("Unhandled exception")


def toTty(tty, sock):
    global run_token
    try:
        while run_token:
            try:
                data = sock.recv(1)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            except TimeoutError:
                log.debug("Timed out on socket")
                continue
            if data:
                log.debug(f"toTty: {data}")
                os.write(tty, data)
    except Exception:
        run_token = False
        log.exception("Unhandled exception")


def kill_conn_and_threads(threads, conn):
    global run_token
    if run_token:
        log.info("Threads already running, kill and close existing connection")
        run_token = False
        for t in threads:
            while True:
                try:
                    t.join()
                except KeyboardInterrupt:
                    continue
                else:
                    break
        if conn:
            conn.close()
        else:
            log.critical("Run token is true, but no existing connection?")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Socket to TTY pipe (server)")
    parser.add_argument("tty", help="Path to tty")
    parser.add_argument("--port", "-p", help="TCP port", default=53123, type=int)
    parser.add_argument("--host", help="TCP host", default="localhost", type=str)
    parser.add_argument("--loglevel", "-log", help="logging level", default="info")

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper())

    s = socket.create_server((args.host, args.port))
    fdtty = os.open(args.tty, os.O_APPEND | os.O_RDWR | os.O_NOCTTY)

    threads = []
    conn = None

    while True:
        try:
            log.info("Waiting for connection...")
            newconn, addr = s.accept()
            newconn.settimeout(1)
            newconn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            newconn.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            log.info(f"New connection from {addr}")

            kill_conn_and_threads(threads, conn)

            run_token = True
            conn = newconn

            thread = threading.Thread(target=toTty, args=[fdtty, conn])
            threads = [thread]
            thread = threading.Thread(target=toSocket, args=[fdtty, conn])
            threads.append(thread)
            for t in threads:
                t.start()
        except KeyboardInterrupt:
            break

    log.info("Shutting down ...")
    kill_conn_and_threads(threads, conn)
    os.close(fdtty)

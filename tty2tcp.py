#!/usr/bin/env python3

import logging
import os
import select
import socket
import threading
import time


class Tty2Tcp:
    def __init__(self, tty_path, port=53123, host="localhost", name=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        self.host = host
        self.port = port
        self.tty_path = tty_path
        self.fdtty = None
        self.main_thread = None
        self.threads = []
        self.conn = None
        self.main_run_token = False
        self.run_token = False
        self.log.info(f"Initializing {name}")

    def start(self):
        if self.main_run_token:
            return

        self.main_thread = threading.Thread(target=self.main)
        self.main_thread.name = (
            f"{self.__class__.__name__}::{self.name}::{self.tty_path}"
        )
        self.log.debug(f"Creating thread: {self.main_thread}")
        self.main_thread.start()

    def stop(self):
        if not self.main_run_token:
            return

        self.main_run_token = False

        self.main_thread.join()

    def main(self):
        self.log.info("Starting server ...")
        s = socket.create_server((self.host, self.port))
        s.settimeout(0.5)
        self.fdtty = os.open(self.tty_path, os.O_APPEND | os.O_RDWR | os.O_NOCTTY)
        self.conn = None
        self.main_run_token = True

        while self.main_run_token:
            try:
                newconn, addr = s.accept()
            except TimeoutError:
                continue
            newconn.settimeout(1)
            newconn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            newconn.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            self.log.info(f"New connection from {addr}")

            self.kill_conn_and_threads()

            self.run_token = True
            self.conn = newconn

            thread = threading.Thread(target=self.toTty)
            thread.name = (
                f"{self.__class__.__name__}::{self.name}::{self.tty_path}::toTty"
            )
            self.threads = [thread]
            thread = threading.Thread(target=self.toSock)
            thread.name = (
                f"{self.__class__.__name__}::{self.name}::{self.tty_path}::toSock"
            )
            self.threads.append(thread)
            for t in self.threads:
                self.log.debug(f"Creating thread: {t}")
                t.start()

        self.log.info("Shutting down ...")
        self.kill_conn_and_threads()
        os.close(self.fdtty)

    def toSock(self):
        try:
            while self.run_token:
                rdy, _, _ = select.select([self.fdtty], [], [], 1)
                try:
                    data = os.read(rdy[0], 1)
                except IndexError:
                    self.log.debug("Timed out on tty")
                    continue
                if data:
                    self.log.debug(f"toSock: {data}")
                    _, rdy, _ = select.select([], [self.conn], [], 0)
                    try:
                        rdy[0].send(data)
                        rdy[0].setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                    except IndexError:
                        self.log.debug("Socket not writable, dropping data")

        except Exception:
            self.run_token = False
            self.main_run_token = False
            self.log.exception("Unhandled exception")

    def toTty(self):
        try:
            while self.run_token:
                try:
                    data = self.conn.recv(1)
                    self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                except TimeoutError:
                    self.log.debug("Timed out on socket")
                    continue
                if data:
                    self.log.debug(f"toTty: {data}")
                    os.write(self.fdtty, data)
        except Exception:
            self.run_token = False
            self.main_run_token = False
            self.log.exception("Unhandled exception")

    def kill_conn_and_threads(self):
        if self.run_token:
            self.log.info("Threads already running, kill and close existing connection")
            self.run_token = False
            for t in self.threads:
                t.join()
            if self.conn:
                self.conn.close()
            else:
                self.log.critical("Run token is true, but no existing connection?")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Socket to TTY pipe (server)")
    parser.add_argument("tty", help="Path to tty")
    parser.add_argument("--port", "-p", help="TCP port", default=53123, type=int)
    parser.add_argument("--host", help="TCP host", default="localhost", type=str)
    parser.add_argument("--loglevel", "-log", help="logging level", default="info")

    args = parser.parse_args()
    log = logging.getLogger(__name__)
    logging.basicConfig(level=args.loglevel.upper())

    bridge = Tty2Tcp(args.tty, args.port, args.host, "server")
    bridge.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            log.info("Ctrl-C received, shutting down")
            break

    bridge.stop()

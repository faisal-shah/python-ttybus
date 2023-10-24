import socket
import threading
import serial
import logging
import time
import sys


log = logging.getLogger(__name__)


run_token = False


def toSock(s, ser):
    global run_token
    try:
        while run_token:
            d = ser.read(1)
            if d:
                try:
                    s.send(d)
                    # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                except TimeoutError:
                    log.critical("Socket OVERFLOW")
            for i in d:
                log.debug(f"TX: {i:02x}")
    except Exception:
        run_token = False
        log.exception("Unhandled exception")


def fromSock(s, ser):
    global run_token
    try:
        while run_token:
            try:
                d = s.recv(1)
                # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            except TimeoutError:
                continue
            if d:
                try:
                    ser.write(d)
                except serial.SerialTimeoutException:
                    log.critical("Serial OVERFLOW")
                    continue
            for i in d:
                log.debug(f"RX: {i:02x}")
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

    parser = argparse.ArgumentParser(description="COM port to TCP (client)")
    parser.add_argument("comport", help="COM port, e.g. COM9")
    parser.add_argument("--baud", "-b", help="Baudrate", default=1000000, type=int)
    parser.add_argument("--port", "-p", help="TCP port", default=53123, type=int)
    parser.add_argument("--host", help="TCP host", default="localhost", type=str)
    parser.add_argument("--loglevel", "-log", help="logging level", default="info")

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper())

    while True:
        try:
            s = socket.create_connection((args.host, args.port), timeout=0.2)
            break
        except TimeoutError:
            log.info("Timed out, retrying")
        except KeyboardInterrupt:
            log.info("Ctrl-C received")
            sys.exit(1)

    log.info("Connected")
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    ser = serial.Serial(
        args.comport, baudrate=args.baud, timeout=0.2, write_timeout=0.2
    )

    thread1 = threading.Thread(target=toSock, args=[s, ser])
    thread2 = threading.Thread(target=fromSock, args=[s, ser])

    run_token = True
    thread1.start()
    thread2.start()

    try:
        while run_token:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Ctrl-C received")

    log.info("Shutting down ...")
    kill_conn_and_threads([thread1, thread2], s)
    ser.close()

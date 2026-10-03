#!/usr/bin/env python3
"""
fake_port.py

Creates a pseudo-terminal and feeds a saved log into it line by line, so
plot_lpc_bins.py's real --port (pyserial) code path can be tested without a
device. Prints the tty path to give to --port, then starts writing once the
reader opens it (or immediately with --no-wait).

Usage:
    # terminal 1
    python3 fake_port.py LPC_DBG_log.txt --speed 20
    #   -> "Fake port ready: /dev/ttys012"
    # terminal 2
    python3 plot_lpc_bins.py --port /dev/ttys012 --baud 115200

Pacing uses the log's [HH:MM:SS.mmm] timestamps (like plot_lpc_bins.py --speed),
skipping the idle/standby gaps. Lines without timestamps are sent with no delay.
Loops forever with --loop.
"""

import argparse
import os
import pty
import time
import tty

from plot_lpc_bins import ENTERING_RE, IDLE_STATES, parse_log_timestamp


def send_log(master_fd, path, speed):
    prev_ts = None
    t_prev_wall = None
    state = None
    with open(path, "r", errors="replace") as f:
        for line in f:
            ts = parse_log_timestamp(line)
            if ts is not None:
                if prev_ts is not None and state not in IDLE_STATES:
                    wait = ((ts - prev_ts) % 86400) / speed - (time.monotonic() - t_prev_wall)
                    if wait > 0:
                        time.sleep(wait)
                prev_ts = ts
                t_prev_wall = time.monotonic()
            m = ENTERING_RE.search(line)
            if m:
                state = m.group(1)
            os.write(master_fd, line.rstrip("\n").encode() + b"\r\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", help="Log file to feed into the fake port")
    parser.add_argument("--speed", type=float, default=1.0, help="Multiple of real time (default: 1)")
    parser.add_argument("--loop", action="store_true", help="Repeat the log forever")
    parser.add_argument("--no-wait", action="store_true", help="Start sending without waiting for a reader to open the port")
    args = parser.parse_args()
    if args.speed <= 0:
        parser.error("--speed must be greater than 0")

    master, slave = pty.openpty()
    tty.setraw(slave)  # no echo / newline translation, like a USB serial device
    print(f"Fake port ready: {os.ttyname(slave)}")
    if not args.no_wait:
        input("Start plot_lpc_bins.py with --port above, then press Enter to begin sending... ")
    try:
        while True:
            send_log(master, args.file, args.speed)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        os.close(master)


if __name__ == "__main__":
    main()

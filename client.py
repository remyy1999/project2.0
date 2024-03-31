#!/usr/bin/env python3

import argparse
import os
import socket
import sys

import confundo

parser = argparse.ArgumentParser("Parser")
parser.add_argument("host", help="Set Hostname")
parser.add_argument("port", help="Set Port Number", type=int)
parser.add_argument("file", help="Set File Directory")
args = parser.parse_args()

def send_message(sock, message):
    # Prefix each message with its length
    message_length = len(message).to_bytes(4, byteorder='big')
    sock.sendall(message_length + message)

def start():
    try:
        with confundo.Socket() as sock:
            sock.settimeout(10)
            sock.connect((args.host, args.port))

            with open(args.file, "rb") as f:
                while True:
                    data = f.read(4096)  # Read 4096 bytes at a time
                    if not data:
                        break  # End of file
                    send_message(sock, data)
    except RuntimeError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    start()

#!/usr/bin/env python3

import argparse
import os
import socket
import sys
import time

from confundo.packet import Packet

parser = argparse.ArgumentParser("Parser")
parser.add_argument("host", help="Set Hostname")
parser.add_argument("port", help="Set Port Number", type=int)
parser.add_argument("file", help="Set File Directory")
args = parser.parse_args()

CHUNK_SIZE = 4096
TIMEOUT = 10  # Timeout in seconds

# Congestion control parameters
CWND_INITIAL = 412
SS_THRESH_INITIAL = 12000

def send_packet(sock, packet, cwnd, ss_thresh):
    packet_str = packet.encode()
    sock.sendto(packet_str, (args.host, args.port))
    flags = ""
    if packet.isAck:
        flags += " ACK"
    if packet.isSyn:
        flags += " SYN"
    if packet.isFin:
        flags += " FIN"
    if packet.isDup:
        flags += " DUP"
    print(f"SEND {packet.seqNum} {packet.ackNum} {packet.connId} {cwnd} {ss_thresh}{flags}")

def receive_packet(sock, cwnd, ss_thresh):
    data, _ = sock.recvfrom(1024)
    packet = Packet().decode(data)
    flags = ""
    if packet.isAck:
        flags += " ACK"
    if packet.isSyn:
        flags += " SYN"
    if packet.isFin:
        flags += " FIN"
    if packet.connId == 0:  # Unknown connection ID, packet dropped
        print(f"DROP {packet.seqNum} {packet.ackNum} {packet.connId}{flags}")
    else:
        print(f"RECV {packet.seqNum} {packet.ackNum} {packet.connId} -1 -1{flags}")
    return packet

def start():
    try:
        # Open a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT)

        # Initialize sequence number to required number
        seq_num = 50000

        # Initialize congestion control variables
        cwnd = CWND_INITIAL
        ss_thresh = SS_THRESH_INITIAL

        # Step 1: Send SYN packet
        syn_packet = Packet(seqNum=seq_num, ackNum=0, connId=261, flags=Packet.FLAG_SYN)
        send_packet(sock, syn_packet, cwnd, ss_thresh)

        # Step 2: Receive SYN | ACK response
        syn_ack_packet = receive_packet(sock, cwnd, ss_thresh)
        if syn_ack_packet.isSynAck():
            conn_id = syn_ack_packet.connId
            seq_num += 1
            
            # Step 3: Send ACK packet
            ack_packet = Packet(seqNum=seq_num, ackNum=syn_ack_packet.seqNum + 1, connId=conn_id, flags=Packet.FLAG_ACK)
            send_packet(sock, ack_packet, cwnd, ss_thresh)

            # Step 4: Send file data in chunks
            with open(args.file, "rb") as f:
                while True:
                    data = f.read(CHUNK_SIZE)
                    if not data:
                        break  # End of file

                    # Send data packet with ACK flag
                    data_packet = Packet(seqNum=seq_num, ackNum=syn_ack_packet.seqNum + 1, connId=conn_id, flags=Packet.FLAG_ACK, payload=data)
                    send_packet(sock, data_packet, cwnd, ss_thresh)
                    
                    # Increment sequence number
                    seq_num += len(data)

                    # Congestion control adjustments after each ACK
                    ack_packet = receive_packet(sock, cwnd, ss_thresh)
                    if ack_packet.isAck():
                        if cwnd < ss_thresh:
                            cwnd += CHUNK_SIZE
                        else:
                            cwnd += (CHUNK_SIZE * CHUNK_SIZE) // cwnd
                    
            # Step 5: Close connection
            sock.close()
            sys.exit(0)
        else:
            raise RuntimeError("Did not receive SYN | ACK packet from server")

    except (socket.gaierror, socket.timeout) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)

    except RuntimeError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    start()

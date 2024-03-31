import struct
import socket
import sys
import time

from enum import Enum
from .common import *

class State(Enum):
    INVALID = 0
    SYN = 1
    OPEN = 3
    LISTEN = 4
    FIN = 10
    FIN_WAIT = 11
    CLOSED = 20
    ERROR = 21

class Socket:
    '''Complete socket abstraction for Confundo protocol'''

    def __init__(self, connId=0, inSeq=0, synReceived=False, sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM), noClose=False):
        self.sock = sock
        self.connId = connId
        self.sock.settimeout(0.5)
        self.timeout = 10

        self.base = 50000
        self.seqNum = self.base
        self.max_seqNum = 50000
        self.ackNum = 0
        self.inSeq = inSeq

        self.lastAckTime = time.time() 
        self.cc = CwndControl()
        self.outBuffer = b""
        self.inBuffer = b""
        self.state = State.INVALID
        self.nDupAcks = 0

        self.synReceived = synReceived
        self.finReceived = False

        self.remote = None
        self.noClose = noClose

        # Initialize congestion control parameters
        self.cwnd = 412  # Initial congestion window size
        self.ssthresh = 12000  # Initial slow start threshold
        self.dup_acks = 0  # Number of duplicate acknowledgments

        # Sliding window parameters
        self.send_window = []  # Stores packets in transit
        self.max_window_size = 10  # Maximum window size
        self.next_seq_num = self.base  # Next sequence number to send
        self.last_acked_seq_num = self.base  # Last acknowledged sequence number

    def connect(self, endpoint):
        remote = socket.getaddrinfo(endpoint[0], endpoint[1], family=socket.AF_INET, type=socket.SOCK_DGRAM)
        (family, type, proto, canonname, sockaddr) = remote[0]

        return self._connect(sockaddr)

    def bind(self, endpoint):
        if self.state != State.INVALID:
            raise RuntimeError()

        remote = socket.getaddrinfo(endpoint[0], endpoint[1], family=socket.AF_INET, type=socket.SOCK_DGRAM)
        (family, type, proto, canonname, sockaddr) = remote[0]

        self.sock.bind(sockaddr)
        self.state = State.LISTEN

    def listen(self, queue):
        if self.state != State.LISTEN:
            raise RuntimeError("Cannot listen")
        pass

    def accept(self):
        if self.state != State.LISTEN:
            raise RuntimeError("Cannot accept")

        hadNewConnId = True
        while True:
            # just wait forever until a new connection arrives

            if hadNewConnId:
                self.connId += 1 # use it for counting incoming connections, no other uses really
                hadNewConnId = False
            pkt = self._recv()
            if pkt and pkt.isSyn:
                hadNewConnId = True
                ### UPDATE CORRECTLY HERE
                clientSock = Socket(connId=self.connId, synReceived=True, sock=self.sock, inSeq=0, noClose=True)
                clientSock._connect(self.lastFromAddr)
                return clientSock

    def settimeout(self, timeout):
        self.timeout = timeout

    def _send(self, packet):
        '''"Private" method to send packet out'''

        if self.remote:
            self.sock.sendto(packet.encode(), self.remote)
        else:
            self.sock.sendto(packet.encode(), self.lastFromAddr)

    def _recv(self):
        '''"Private" method to receive incoming packets'''

        try:
            (inPacket, self.lastFromAddr) = self.sock.recvfrom(1024)
        except socket.error as e:
            return None

        inPkt = Packet().decode(inPacket)

        outPkt = None
        if inPkt.isSyn:
            if inPkt.connId != 0:
                self.connId = inPkt.connId
            self.synReceived = True
            outPkt = Packet(seqNum=self.seqNum, ackNum=self.inSeq, connId=self.connId, isAck=True)

        elif inPkt.isFin:
            if self.inSeq == inPkt.seqNum:
                self.finReceived = True

            outPkt = Packet(seqNum=self.seqNum, ackNum=self.inSeq, connId=self.connId, isAck=True)

        elif len(inPkt.payload) > 0:
            if not self.synReceived:
                raise RuntimeError("Receiving data before SYN received")
            if self.finReceived:
                raise RuntimeError("Received data after getting FIN (incoming connection closed)")
            self.inBuffer += inPkt.payload
            outPkt = Packet(seqNum=self.seqNum, ackNum=inPkt.seqNum, connId=self.connId, isAck=True)

        if outPkt:
            self._send(outPkt)

        return inPkt

    def _connect(self, remote):
        self.remote = remote
        if self.state != State.INVALID:
            raise RuntimeError("Trying to connect, but socket is already opened")
        self.sendSynPacket()
        self.state = State.SYN
        self.expectSynAck()

    def close(self):
        if self.state != State.OPEN:
            raise RuntimeError("Trying to send FIN, but socket is not in OPEN state")
        self.sendFinPacket()
        self.state = State.FIN
        self.expectFinAck()

    def sendSynPacket(self):
        synPkt = Packet(seqNum=self.seqNum, connId=self.connId, isSyn=True)
        self._send(synPkt)

    def expectSynAck(self):
        startTime = time.time()
        while True:
            pkt = self._recv()
            if pkt and pkt.isAck and pkt.ackNum == self.seqNum:
                self.base = self.seqNum
                self.state = State.OPEN
                break
            if time.time() - startTime > GLOBAL_TIMEOUT:
                self.state = State.ERROR
                raise RuntimeError("timeout")

    def sendFinPacket(self):
        synPkt = Packet(seqNum=self.seqNum, connId=self.connId, isFin=True)
        self._send(synPkt)

    def expectFinAck(self):
        startTime = time.time()
        while True:
            pkt = self._recv()
            if pkt and pkt.isAck and pkt.ackNum == self.seqNum:
                self.base = self.seqNum
                self.state = State.CLOSED
                break
            if time.time() - startTime > GLOBAL_TIMEOUT:
                return

    def recv(self, maxSize):
        startTime = time.time()
        while len(self.inBuffer) == 0:
            self._recv()
            if self.finReceived:
                return None
            if time.time() - startTime > GLOBAL_TIMEOUT:
                self.state = State.ERROR
                raise RuntimeError("timeout")
        if len(self.inBuffer) > 0:
            actualResponseSize = min(len(self.inBuffer), maxSize)
            response = self.inBuffer[:actualResponseSize]
            self.inBuffer = self.inBuffer[actualResponseSize:]
            return response

    def send(self, data):
        if self.state != State.OPEN:
            raise RuntimeError("Trying to send FIN, but socket is not in OPEN state")
        self.outBuffer += data
        startTime = time.time()
        while len(self.outBuffer) > 0:
            toSend = self.outBuffer[:MTU]
            pkt = Packet(seqNum=self.seqNum, connId=self.connId, payload=toSend)
            self._send(pkt)
            pkt = self._recv() 
            if pkt and pkt.isAck:
                advanceAmount = pkt.ackNum - self.seqNum
                if advanceAmount == 0:
                    self.nDupAcks += 1
                else:
                    self.nDupAcks = 0
                self.outBuffer = self.outBuffer[advanceAmount:]
                self.seqNum += advanceAmount
            if time.time() - startTime > GLOBAL_TIMEOUT:
                self.state = State.ERROR
                raise RuntimeError("timeout")
        return len(data)


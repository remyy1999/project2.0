# -*- Mode: python; py-indent-offset: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# Copyright 2019 Alex Afanasyev
#

from .header import Header

class Packet(Header):
    '''Abstraction to handle the whole Confundo packet (e.g., with payload, if present)'''

    def __init__(self, seqNum=0, ackNum=0, connId=0, flags=0, payload=b"", **kwargs):
        super(Packet, self).__init__(seqNum=seqNum, ackNum=ackNum, connId=connId, flags=flags, **kwargs)
        self.payload = payload

    def decode(self, fullPacket):
        super(Packet, self).decode(fullPacket[:12])
        self.payload = fullPacket[12:]
        return self

    def encode(self):
        header = super(Packet, self).encode()
        return header + self.payload

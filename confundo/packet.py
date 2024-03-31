from .header import Header

class Packet(Header):
    '''Abstraction to handle the whole Confundo packet (e.g., with payload, if present)'''

    # Define flags as class attributes
    FLAG_SYN = "SYN"
    FLAG_ACK = "ACK"
    FLAG_FIN = "FIN"

    def __init__(self, payload=b"", flags=None, isDup=False, **kwargs):
        super(Packet, self).__init__(**kwargs)
        self.payload = payload
        self.flags = flags
        self.isDup = isDup # only for printing flags

    def decode(self, fullPacket):
        super(Packet, self).decode(fullPacket[0:12])
        self.payload = fullPacket[12:]
        return self

    def encode(self):
        return super(Packet, self).encode() + self.payload


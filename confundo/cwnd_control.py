from .common import MTU, INIT_SSTHRESH

class CwndControl:
    '''Interface for the congestion control actions'''

    def __init__(self):
        self.cwnd = 1.0 * MTU  # Initial congestion window size
        self.ssthresh = INIT_SSTHRESH  # Initial slow start threshold

    def on_ack(self, ackedDataLen):
        # Adjust congestion window size and slow start threshold based on the acknowledgment
        if self.cwnd < self.ssthresh:
            # Slow start phase
            self.cwnd += ackedDataLen
        else:
            # Congestion avoidance phase
            self.cwnd += (MTU * MTU) // self.cwnd

    def on_timeout(self):
        # Reduce congestion window size and set slow start threshold after a timeout
        self.ssthresh = max(self.cwnd / 2, INIT_SSTHRESH)  # Set slow start threshold to half of current window size or to initial threshold
        self.cwnd = 1.0 * MTU  # Reset congestion window size to 1 MTU after timeout


class Receiver:
    def __init__(self):
        self.channels = {}

    def update_channel(self, channel, value):
        self.channels[channel] = value

    def get_channel(self, channel):
        return self.channels.get(channel, None)

    def get_all_channels(self):
        return self.channels

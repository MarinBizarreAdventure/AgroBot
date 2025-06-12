class ChannelMapper:
    def __init__(self, channel_map=None):
        self.channel_map = channel_map or {}

    def set_channel(self, name, value):
        self.channel_map[name] = value

    def get_channel(self, name):
        return self.channel_map.get(name, None)

    def all_channels(self):
        return self.channel_map

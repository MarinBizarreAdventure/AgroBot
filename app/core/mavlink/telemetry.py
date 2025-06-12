class TelemetryManager:
    def __init__(self):
        self.gps = None
        self.attitude = None
        self.battery = None

    def update_gps(self, gps_data):
        self.gps = gps_data

    def update_attitude(self, attitude_data):
        self.attitude = attitude_data

    def update_battery(self, battery_data):
        self.battery = battery_data

    def get_telemetry(self):
        return {
            'gps': self.gps,
            'attitude': self.attitude,
            'battery': self.battery
        }

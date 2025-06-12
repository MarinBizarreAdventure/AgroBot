class WaypointManager:
    def __init__(self):
        self.waypoints = []

    def add_waypoint(self, lat, lon, alt):
        self.waypoints.append({'lat': lat, 'lon': lon, 'alt': alt})

    def remove_waypoint(self, index):
        if 0 <= index < len(self.waypoints):
            self.waypoints.pop(index)

    def list_waypoints(self):
        return self.waypoints

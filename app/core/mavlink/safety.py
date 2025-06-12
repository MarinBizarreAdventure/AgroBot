class SafetyManager:
    def __init__(self, geofence=None):
        self.geofence = geofence or []  # List of (lat, lon) tuples
        self.emergency_stopped = False

    def check_arming(self, system_status):
        # Example: Check if all pre-arm checks are passed
        return system_status.get('prearm_check', True)

    def validate_geofence(self, lat, lon):
        # Simple geofence: bounding box
        if not self.geofence:
            return True
        min_lat = min(p[0] for p in self.geofence)
        max_lat = max(p[0] for p in self.geofence)
        min_lon = min(p[1] for p in self.geofence)
        max_lon = max(p[1] for p in self.geofence)
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

    def trigger_emergency_stop(self):
        self.emergency_stopped = True
        # Add logic to send emergency stop to Pixhawk
        return True

    def reset_emergency_stop(self):
        self.emergency_stopped = False
        return True

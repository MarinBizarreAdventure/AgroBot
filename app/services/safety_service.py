from app.core.mavlink.safety import SafetyManager

class SafetyService:
    def __init__(self, geofence=None):
        self.safety_manager = SafetyManager(geofence)

    def check_arming(self, system_status):
        return self.safety_manager.check_arming(system_status)

    def validate_geofence(self, lat, lon):
        return self.safety_manager.validate_geofence(lat, lon)

    def trigger_emergency_stop(self):
        return self.safety_manager.trigger_emergency_stop()

    def reset_emergency_stop(self):
        return self.safety_manager.reset_emergency_stop()

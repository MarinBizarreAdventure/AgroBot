from app.core.mission.planner import MissionPlanner
from app.core.mission.waypoints import WaypointManager
from app.core.mission.patterns import PatternGenerator

class MissionService:
    def __init__(self):
        self.waypoint_manager = WaypointManager()
        self.pattern_generator = PatternGenerator()
        self.planner = MissionPlanner(self.waypoint_manager, self.pattern_generator)

    def create_mission(self, waypoints):
        self.planner.create_mission(waypoints)
        return self.planner.get_current_mission()

    def execute_mission(self):
        return self.planner.execute_mission()

    def get_current_mission(self):
        return self.planner.get_current_mission()

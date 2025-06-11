"""
GPS utility functions and coordinate transformations
"""

import math
import time
import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Earth constants
EARTH_RADIUS = 6371000  # meters
WGS84_A = 6378137.0  # Semi-major axis
WGS84_F = 1/298.257223563  # Flattening
WGS84_E2 = 2*WGS84_F - WGS84_F**2  # First eccentricity squared


@dataclass
class Coordinate:
    """GPS coordinate with metadata"""
    latitude: float
    longitude: float
    altitude: float = 0.0
    timestamp: float = 0.0
    accuracy: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class BoundingBox:
    """Geographic bounding box"""
    north: float
    south: float
    east: float
    west: float
    
    def contains(self, lat: float, lon: float) -> bool:
        """Check if coordinate is within bounding box"""
        return (self.south <= lat <= self.north and 
                self.west <= lon <= self.east)
    
    def center(self) -> Tuple[float, float]:
        """Get center point of bounding box"""
        center_lat = (self.north + self.south) / 2
        center_lon = (self.east + self.west) / 2
        return center_lat, center_lon


class CoordinateConverter:
    """Coordinate system conversions"""
    
    @staticmethod
    def decimal_to_dms(decimal_degrees: float) -> Tuple[int, int, float]:
        """
        Convert decimal degrees to degrees, minutes, seconds
        
        Args:
            decimal_degrees: Coordinate in decimal degrees
            
        Returns:
            Tuple of (degrees, minutes, seconds)
        """
        abs_degrees = abs(decimal_degrees)
        degrees = int(abs_degrees)
        minutes_float = (abs_degrees - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        
        return degrees, minutes, seconds
    
    @staticmethod
    def dms_to_decimal(degrees: int, minutes: int, seconds: float, 
                      direction: str = 'N') -> float:
        """
        Convert degrees, minutes, seconds to decimal degrees
        
        Args:
            degrees: Degrees component
            minutes: Minutes component
            seconds: Seconds component
            direction: Direction (N/S for latitude, E/W for longitude)
            
        Returns:
            Coordinate in decimal degrees
        """
        decimal = degrees + minutes/60 + seconds/3600
        
        if direction.upper() in ['S', 'W']:
            decimal = -decimal
            
        return decimal
    
    @staticmethod
    def format_coordinate(lat: float, lon: float, format_type: str = 'decimal') -> str:
        """
        Format coordinates for display
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            format_type: Format type ('decimal', 'dms', 'dm')
            
        Returns:
            Formatted coordinate string
        """
        if format_type == 'decimal':
            return f"{lat:.6f}, {lon:.6f}"
        
        elif format_type == 'dms':
            lat_d, lat_m, lat_s = CoordinateConverter.decimal_to_dms(lat)
            lon_d, lon_m, lon_s = CoordinateConverter.decimal_to_dms(lon)
            lat_dir = 'N' if lat >= 0 else 'S'
            lon_dir = 'E' if lon >= 0 else 'W'
            
            return f"{lat_d}°{lat_m}'{lat_s:.2f}\"{lat_dir}, {lon_d}°{lon_m}'{lon_s:.2f}\"{lon_dir}"
        
        elif format_type == 'dm':
            lat_d, lat_m, _ = CoordinateConverter.decimal_to_dms(lat)
            lon_d, lon_m, _ = CoordinateConverter.decimal_to_dms(lon)
            lat_dir = 'N' if lat >= 0 else 'S'
            lon_dir = 'E' if lon >= 0 else 'W'
            
            lat_m_decimal = (abs(lat) - abs(lat_d)) * 60
            lon_m_decimal = (abs(lon) - abs(lon_d)) * 60
            
            return f"{lat_d}°{lat_m_decimal:.4f}'{lat_dir}, {lon_d}°{lon_m_decimal:.4f}'{lon_dir}"
        
        else:
            raise ValueError(f"Unknown format type: {format_type}")


class DistanceCalculator:
    """Distance and bearing calculation utilities"""
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return EARTH_RADIUS * c
    
    @staticmethod
    def vincenty_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance using Vincenty's formula (more accurate)
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        # Vincenty's formula
        a = WGS84_A
        b = a * (1 - WGS84_F)
        f = WGS84_F
        
        L = delta_lon
        U1 = math.atan((1 - f) * math.tan(lat1_rad))
        U2 = math.atan((1 - f) * math.tan(lat2_rad))
        
        sin_U1 = math.sin(U1)
        cos_U1 = math.cos(U1)
        sin_U2 = math.sin(U2)
        cos_U2 = math.cos(U2)
        
        lambda_val = L
        lambda_prev = 2 * math.pi
        iter_limit = 100
        
        while abs(lambda_val - lambda_prev) > 1e-12 and iter_limit > 0:
            sin_lambda = math.sin(lambda_val)
            cos_lambda = math.cos(lambda_val)
            
            sin_sigma = math.sqrt((cos_U2 * sin_lambda) ** 2 +
                                (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda) ** 2)
            
            if sin_sigma == 0:
                return 0  # Coincident points
            
            cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lambda
            sigma = math.atan2(sin_sigma, cos_sigma)
            
            sin_alpha = cos_U1 * cos_U2 * sin_lambda / sin_sigma
            cos2_alpha = 1 - sin_alpha ** 2
            
            cos_2sigma_m = cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha
            
            C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
            
            lambda_prev = lambda_val
            lambda_val = L + (1 - C) * f * sin_alpha * \
                       (sigma + C * sin_sigma * (cos_2sigma_m + C * cos_sigma * (-1 + 2 * cos_2sigma_m ** 2)))
            
            iter_limit -= 1
        
        if iter_limit == 0:
            return float('nan')  # Formula failed to converge
        
        u2 = cos2_alpha * (a ** 2 - b ** 2) / (b ** 2)
        A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
        B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
        
        delta_sigma = B * sin_sigma * (cos_2sigma_m + B / 4 * (cos_sigma * (-1 + 2 * cos_2sigma_m ** 2) -
                                                             B / 6 * cos_2sigma_m * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos_2sigma_m ** 2)))
        
        distance = b * A * (sigma - delta_sigma)
        
        return distance
    
    @staticmethod
    def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate initial bearing from point 1 to point 2
        
        Args:
            lat1, lon1: Start point coordinates
            lat2, lon2: End point coordinates
            
        Returns:
            Bearing in degrees (0-360)
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
        
        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360  # Normalize to 0-360
        
        return bearing
    
    @staticmethod
    def destination_point(lat: float, lon: float, bearing: float, distance: float) -> Tuple[float, float]:
        """
        Calculate destination point given start point, bearing, and distance
        
        Args:
            lat, lon: Start point coordinates
            bearing: Bearing in degrees
            distance: Distance in meters
            
        Returns:
            Destination point as (latitude, longitude)
        """
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        bearing_rad = math.radians(bearing)
        
        # Angular distance
        angular_distance = distance / EARTH_RADIUS
        
        # Calculate destination
        dest_lat = math.asin(
            math.sin(lat_rad) * math.cos(angular_distance) +
            math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        
        dest_lon = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
            math.cos(angular_distance) - math.sin(lat_rad) * math.sin(dest_lat)
        )
        
        return math.degrees(dest_lat), math.degrees(dest_lon)
    
    @staticmethod
    def midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
        """
        Calculate midpoint between two coordinates
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Midpoint as (latitude, longitude)
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        bx = math.cos(lat2_rad) * math.cos(delta_lon)
        by = math.cos(lat2_rad) * math.sin(delta_lon)
        
        lat3 = math.atan2(
            math.sin(lat1_rad) + math.sin(lat2_rad),
            math.sqrt((math.cos(lat1_rad) + bx) * (math.cos(lat1_rad) + bx) + by * by)
        )
        
        lon3 = math.radians(lon1) + math.atan2(by, math.cos(lat1_rad) + bx)
        
        return math.degrees(lat3), math.degrees(lon3)


class GeofenceUtils:
    """Geofence utility functions"""
    
    @staticmethod
    def point_in_circle(lat: float, lon: float, center_lat: float, 
                       center_lon: float, radius: float) -> bool:
        """
        Check if point is within circular geofence
        
        Args:
            lat, lon: Point to check
            center_lat, center_lon: Geofence center
            radius: Geofence radius in meters
            
        Returns:
            True if point is inside geofence
        """
        distance = DistanceCalculator.haversine_distance(lat, lon, center_lat, center_lon)
        return distance <= radius
    
    @staticmethod
    def point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
        """
        Check if point is within polygon geofence using ray casting
        
        Args:
            lat, lon: Point to check
            polygon: List of (lat, lon) tuples defining polygon vertices
            
        Returns:
            True if point is inside polygon
        """
        x, y = lon, lat
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    @staticmethod
    def distance_to_boundary(lat: float, lon: float, center_lat: float,
                           center_lon: float, radius: float) -> float:
        """
        Calculate distance to circular geofence boundary
        
        Args:
            lat, lon: Current position
            center_lat, center_lon: Geofence center
            radius: Geofence radius
            
        Returns:
            Distance to boundary (negative if outside)
        """
        distance_to_center = DistanceCalculator.haversine_distance(lat, lon, center_lat, center_lon)
        return radius - distance_to_center


class PathUtils:
    """Path planning and optimization utilities"""
    
    @staticmethod
    def calculate_path_length(waypoints: List[Tuple[float, float]]) -> float:
        """
        Calculate total path length for list of waypoints
        
        Args:
            waypoints: List of (lat, lon) tuples
            
        Returns:
            Total path length in meters
        """
        if len(waypoints) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(waypoints)):
            prev_lat, prev_lon = waypoints[i-1]
            curr_lat, curr_lon = waypoints[i]
            
            distance = DistanceCalculator.haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
            total_distance += distance
        
        return total_distance
    
    @staticmethod
    def simplify_path(waypoints: List[Tuple[float, float]], tolerance: float = 2.0) -> List[Tuple[float, float]]:
        """
        Simplify path using Douglas-Peucker algorithm
        
        Args:
            waypoints: List of (lat, lon) tuples
            tolerance: Tolerance in meters
            
        Returns:
            Simplified path
        """
        if len(waypoints) <= 2:
            return waypoints
        
        # Convert tolerance from meters to degrees (rough approximation)
        tolerance_deg = tolerance / 111320  # meters per degree at equator
        
        def perpendicular_distance(point: Tuple[float, float], line_start: Tuple[float, float], 
                                 line_end: Tuple[float, float]) -> float:
            """Calculate perpendicular distance from point to line"""
            x0, y0 = point
            x1, y1 = line_start
            x2, y2 = line_end
            
            if x1 == x2 and y1 == y2:
                return math.sqrt((x0 - x1)**2 + (y0 - y1)**2)
            
            num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
            den = math.sqrt((y2 - y1)**2 + (x2 - x1)**2)
            
            return num / den
        
        def douglas_peucker(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
            """Douglas-Peucker simplification algorithm"""
            if len(points) <= 2:
                return points
            
            # Find the point with maximum distance
            max_distance = 0
            max_index = 0
            
            for i in range(1, len(points) - 1):
                distance = perpendicular_distance(points[i], points[0], points[-1])
                if distance > max_distance:
                    max_distance = distance
                    max_index = i
            
            # If max distance is greater than epsilon, recursively simplify
            if max_distance > epsilon:
                # Recursive call
                left_part = douglas_peucker(points[:max_index + 1], epsilon)
                right_part = douglas_peucker(points[max_index:], epsilon)
                
                # Combine results
                return left_part[:-1] + right_part
            else:
                return [points[0], points[-1]]
        
        return douglas_peucker(waypoints, tolerance_deg)
    
    @staticmethod
    def generate_grid_waypoints(bounds: BoundingBox, spacing: float, 
                              altitude: float = 10.0) -> List[Dict[str, Any]]:
        """
        Generate grid pattern waypoints within bounding box
        
        Args:
            bounds: Bounding box for grid
            spacing: Grid spacing in meters
            altitude: Flight altitude
            
        Returns:
            List of waypoint dictionaries
        """
        waypoints = []
        
        # Convert spacing from meters to degrees (rough approximation)
        lat_spacing = spacing / 111320  # meters per degree latitude
        lon_spacing = spacing / (111320 * math.cos(math.radians(bounds.center()[0])))  # adjust for longitude
        
        # Generate grid points
        lat = bounds.south
        row = 0
        
        while lat <= bounds.north:
            if row % 2 == 0:  # Left to right
                lon = bounds.west
                while lon <= bounds.east:
                    waypoints.append({
                        'latitude': lat,
                        'longitude': lon,
                        'altitude': altitude,
                        'sequence': len(waypoints)
                    })
                    lon += lon_spacing
            else:  # Right to left
                lon = bounds.east
                while lon >= bounds.west:
                    waypoints.append({
                        'latitude': lat,
                        'longitude': lon,
                        'altitude': altitude,
                        'sequence': len(waypoints)
                    })
                    lon -= lon_spacing
            
            lat += lat_spacing
            row += 1
        
        return waypoints
    
    @staticmethod
    def generate_circle_waypoints(center_lat: float, center_lon: float, 
                                radius: float, num_points: int = 8,
                                altitude: float = 10.0, clockwise: bool = True) -> List[Dict[str, Any]]:
        """
        Generate circular pattern waypoints
        
        Args:
            center_lat, center_lon: Circle center
            radius: Circle radius in meters
            num_points: Number of waypoints
            altitude: Flight altitude
            clockwise: Direction of flight
            
        Returns:
            List of waypoint dictionaries
        """
        waypoints = []
        angle_step = 360.0 / num_points
        
        for i in range(num_points):
            angle = i * angle_step
            if not clockwise:
                angle = 360 - angle
            
            lat, lon = DistanceCalculator.destination_point(center_lat, center_lon, angle, radius)
            
            waypoints.append({
                'latitude': lat,
                'longitude': lon,
                'altitude': altitude,
                'sequence': i
            })
        
        return waypoints


class GPSQualityAssessment:
    """GPS signal quality assessment utilities"""
    
    @staticmethod
    def assess_fix_quality(satellites: int, hdop: float, fix_type: int) -> Dict[str, Any]:
        """
        Assess GPS fix quality
        
        Args:
            satellites: Number of satellites
            hdop: Horizontal dilution of precision
            fix_type: GPS fix type
            
        Returns:
            Quality assessment dictionary
        """
        # Base score
        score = 0
        
        # Satellite count scoring
        if satellites >= 8:
            score += 40
        elif satellites >= 6:
            score += 30
        elif satellites >= 4:
            score += 20
        else:
            score += 10
        
        # HDOP scoring
        if hdop <= 1.0:
            score += 30
        elif hdop <= 2.0:
            score += 25
        elif hdop <= 5.0:
            score += 15
        else:
            score += 5
        
        # Fix type scoring
        if fix_type >= 3:  # 3D fix
            score += 30
        elif fix_type == 2:  # 2D fix
            score += 15
        else:
            score += 0
        
        # Determine quality level
        if score >= 85:
            quality = "excellent"
        elif score >= 70:
            quality = "good"
        elif score >= 50:
            quality = "fair"
        else:
            quality = "poor"
        
        # Navigation suitability
        navigation_ready = (fix_type >= 3 and satellites >= 6 and hdop <= 2.0)
        
        return {
            "score": score,
            "quality": quality,
            "navigation_ready": navigation_ready,
            "satellites": satellites,
            "hdop": hdop,
            "fix_type": fix_type,
            "recommendations": GPSQualityAssessment._get_recommendations(satellites, hdop, fix_type)
        }
    
    @staticmethod
    def _get_recommendations(satellites: int, hdop: float, fix_type: int) -> List[str]:
        """Get recommendations for improving GPS quality"""
        recommendations = []
        
        if satellites < 6:
            recommendations.append("Move to area with better sky visibility")
        
        if hdop > 2.0:
            recommendations.append("Wait for better satellite geometry")
        
        if fix_type < 3:
            recommendations.append("Ensure GPS has clear view of sky")
        
        if not recommendations:
            recommendations.append("GPS quality is good for navigation")
        
        return recommendations
    
    @staticmethod
    def estimate_position_error(hdop: float, fix_type: int) -> float:
        """
        Estimate position error in meters
        
        Args:
            hdop: Horizontal dilution of precision
            fix_type: GPS fix type
            
        Returns:
            Estimated position error in meters
        """
        # Base error for GPS
        base_error = 3.0  # meters (typical GPS accuracy)
        
        # Apply HDOP multiplier
        error = base_error * hdop
        
        # Apply fix type multiplier
        if fix_type >= 3:  # 3D fix
            multiplier = 1.0
        elif fix_type == 2:  # 2D fix
            multiplier = 2.0
        else:  # No fix
            multiplier = 10.0
        
        return error * multiplier
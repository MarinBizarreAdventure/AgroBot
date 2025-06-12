class PatternGenerator:
    def generate_square(self, center_lat, center_lon, size, alt):
        # Returns waypoints for a square pattern
        half = size / 2.0
        return [
            {'lat': center_lat - half, 'lon': center_lon - half, 'alt': alt},
            {'lat': center_lat - half, 'lon': center_lon + half, 'alt': alt},
            {'lat': center_lat + half, 'lon': center_lon + half, 'alt': alt},
            {'lat': center_lat + half, 'lon': center_lon - half, 'alt': alt},
            {'lat': center_lat - half, 'lon': center_lon - half, 'alt': alt},
        ]

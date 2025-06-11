"""
GPS data parsing and processing utilities
"""

import re
import math
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class GPSFix:
    """GPS fix data structure"""
    timestamp: float
    latitude: float
    longitude: float
    altitude: float
    speed: float
    course: float
    satellites: int
    hdop: float
    vdop: float
    fix_type: int
    fix_quality: str


@dataclass
class NMEASentence:
    """NMEA sentence data structure"""
    sentence_type: str
    raw_data: str
    timestamp: float
    checksum_valid: bool
    fields: List[str]


class NMEAParser:
    """NMEA 0183 sentence parser"""
    
    def __init__(self):
        self.sentence_handlers = {
            'GPGGA': self._parse_gga,
            'GPRMC': self._parse_rmc,
            'GPGSA': self._parse_gsa,
            'GPGSV': self._parse_gsv,
            'GPVTG': self._parse_vtg,
            'GPGLL': self._parse_gll
        }
        
        # Parsing statistics
        self.sentences_parsed = 0
        self.sentences_failed = 0
        self.checksum_errors = 0
        
    def parse_sentence(self, sentence: str) -> Optional[NMEASentence]:
        """
        Parse a single NMEA sentence
        
        Args:
            sentence: Raw NMEA sentence string
            
        Returns:
            NMEASentence object or None if parsing failed
        """
        try:
            sentence = sentence.strip()
            
            # Check if sentence starts with $
            if not sentence.startswith('$'):
                return None
            
            # Split sentence and checksum
            if '*' in sentence:
                sentence_part, checksum_part = sentence.rsplit('*', 1)
                expected_checksum = checksum_part.upper()
                calculated_checksum = self._calculate_checksum(sentence_part[1:])
                checksum_valid = expected_checksum == calculated_checksum
                
                if not checksum_valid:
                    self.checksum_errors += 1
            else:
                sentence_part = sentence
                checksum_valid = True
            
            # Split into fields
            fields = sentence_part[1:].split(',')
            sentence_type = fields[0] if fields else ""
            
            self.sentences_parsed += 1
            
            return NMEASentence(
                sentence_type=sentence_type,
                raw_data=sentence,
                timestamp=time.time(),
                checksum_valid=checksum_valid,
                fields=fields
            )
            
        except Exception as e:
            logger.debug(f"Error parsing NMEA sentence: {e}")
            self.sentences_failed += 1
            return None
    
    def _calculate_checksum(self, sentence: str) -> str:
        """Calculate NMEA checksum"""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"
    
    def parse_gps_data(self, sentence: str) -> Optional[Dict[str, Any]]:
        """
        Parse NMEA sentence and extract GPS data
        
        Args:
            sentence: Raw NMEA sentence
            
        Returns:
            Dictionary with parsed GPS data or None
        """
        nmea_sentence = self.parse_sentence(sentence)
        if not nmea_sentence or not nmea_sentence.checksum_valid:
            return None
        
        # Get appropriate handler
        handler = self.sentence_handlers.get(nmea_sentence.sentence_type)
        if handler:
            try:
                return handler(nmea_sentence.fields)
            except Exception as e:
                logger.debug(f"Error parsing {nmea_sentence.sentence_type}: {e}")
        
        return None
    
    def _parse_gga(self, fields: List[str]) -> Dict[str, Any]:
        """Parse GGA sentence (Global Positioning System Fix Data)"""
        if len(fields) < 15:
            return {}
        
        # Extract time
        time_str = fields[1]
        utc_time = self._parse_time(time_str)
        
        # Extract coordinates
        lat = self._parse_coordinate(fields[2], fields[3])
        lon = self._parse_coordinate(fields[4], fields[5])
        
        # Extract other data
        fix_quality = int(fields[6]) if fields[6] else 0
        satellites = int(fields[7]) if fields[7] else 0
        hdop = float(fields[8]) if fields[8] else 99.9
        altitude = float(fields[9]) if fields[9] else 0.0
        
        return {
            'type': 'GGA',
            'utc_time': utc_time,
            'latitude': lat,
            'longitude': lon,
            'fix_quality': fix_quality,
            'satellites': satellites,
            'hdop': hdop,
            'altitude': altitude,
            'altitude_units': fields[10],
            'geoid_height': float(fields[11]) if fields[11] else 0.0,
            'timestamp': time.time()
        }
    
    def _parse_rmc(self, fields: List[str]) -> Dict[str, Any]:
        """Parse RMC sentence (Recommended Minimum Course)"""
        if len(fields) < 12:
            return {}
        
        # Extract time and date
        time_str = fields[1]
        date_str = fields[9]
        utc_time = self._parse_time(time_str)
        utc_date = self._parse_date(date_str)
        
        # Extract coordinates
        lat = self._parse_coordinate(fields[3], fields[4])
        lon = self._parse_coordinate(fields[5], fields[6])
        
        # Extract speed and course
        speed_knots = float(fields[7]) if fields[7] else 0.0
        course = float(fields[8]) if fields[8] else 0.0
        
        # Convert speed from knots to m/s
        speed_ms = speed_knots * 0.514444
        
        return {
            'type': 'RMC',
            'utc_time': utc_time,
            'utc_date': utc_date,
            'status': fields[2],  # A = valid, V = invalid
            'latitude': lat,
            'longitude': lon,
            'speed_knots': speed_knots,
            'speed_ms': speed_ms,
            'course': course,
            'magnetic_variation': float(fields[10]) if fields[10] else 0.0,
            'timestamp': time.time()
        }
    
    def _parse_gsa(self, fields: List[str]) -> Dict[str, Any]:
        """Parse GSA sentence (GPS DOP and active satellites)"""
        if len(fields) < 18:
            return {}
        
        mode = fields[1]  # M = manual, A = automatic
        fix_type = int(fields[2]) if fields[2] else 1
        
        # Satellite IDs (up to 12)
        satellites = []
        for i in range(3, 15):
            if fields[i]:
                satellites.append(int(fields[i]))
        
        # DOP values
        pdop = float(fields[15]) if fields[15] else 99.9
        hdop = float(fields[16]) if fields[16] else 99.9
        vdop = float(fields[17]) if fields[17] else 99.9
        
        return {
            'type': 'GSA',
            'mode': mode,
            'fix_type': fix_type,
            'satellites': satellites,
            'pdop': pdop,
            'hdop': hdop,
            'vdop': vdop,
            'timestamp': time.time()
        }
    
    def _parse_gsv(self, fields: List[str]) -> Dict[str, Any]:
        """Parse GSV sentence (GPS satellites in view)"""
        if len(fields) < 4:
            return {}
        
        total_sentences = int(fields[1]) if fields[1] else 1
        sentence_number = int(fields[2]) if fields[2] else 1
        total_satellites = int(fields[3]) if fields[3] else 0
        
        # Parse satellite information (up to 4 satellites per sentence)
        satellites = []
        for i in range(4, len(fields), 4):
            if i + 3 < len(fields):
                sat_id = fields[i] if fields[i] else None
                elevation = int(fields[i + 1]) if fields[i + 1] else None
                azimuth = int(fields[i + 2]) if fields[i + 2] else None
                snr = int(fields[i + 3]) if fields[i + 3] else None
                
                if sat_id:
                    satellites.append({
                        'id': int(sat_id),
                        'elevation': elevation,
                        'azimuth': azimuth,
                        'snr': snr
                    })
        
        return {
            'type': 'GSV',
            'total_sentences': total_sentences,
            'sentence_number': sentence_number,
            'total_satellites': total_satellites,
            'satellites': satellites,
            'timestamp': time.time()
        }
    
    def _parse_vtg(self, fields: List[str]) -> Dict[str, Any]:
        """Parse VTG sentence (Track made good and Ground speed)"""
        if len(fields) < 9:
            return {}
        
        true_course = float(fields[1]) if fields[1] else 0.0
        magnetic_course = float(fields[3]) if fields[3] else 0.0
        speed_knots = float(fields[5]) if fields[5] else 0.0
        speed_kmh = float(fields[7]) if fields[7] else 0.0
        
        # Convert to m/s
        speed_ms = speed_knots * 0.514444
        
        return {
            'type': 'VTG',
            'true_course': true_course,
            'magnetic_course': magnetic_course,
            'speed_knots': speed_knots,
            'speed_kmh': speed_kmh,
            'speed_ms': speed_ms,
            'timestamp': time.time()
        }
    
    def _parse_gll(self, fields: List[str]) -> Dict[str, Any]:
        """Parse GLL sentence (Geographic position)"""
        if len(fields) < 7:
            return {}
        
        lat = self._parse_coordinate(fields[1], fields[2])
        lon = self._parse_coordinate(fields[3], fields[4])
        utc_time = self._parse_time(fields[5])
        status = fields[6]  # A = valid, V = invalid
        
        return {
            'type': 'GLL',
            'latitude': lat,
            'longitude': lon,
            'utc_time': utc_time,
            'status': status,
            'timestamp': time.time()
        }
    
    def _parse_coordinate(self, coord_str: str, direction: str) -> Optional[float]:
        """Parse coordinate from NMEA format to decimal degrees"""
        if not coord_str or not direction:
            return None
        
        try:
            # NMEA format: DDMM.MMMM or DDDMM.MMMM
            if len(coord_str) >= 7:  # Longitude format
                degrees = int(coord_str[:3])
                minutes = float(coord_str[3:])
            else:  # Latitude format
                degrees = int(coord_str[:2])
                minutes = float(coord_str[2:])
            
            decimal_degrees = degrees + minutes / 60.0
            
            # Apply direction
            if direction in ['S', 'W']:
                decimal_degrees = -decimal_degrees
            
            return decimal_degrees
            
        except (ValueError, IndexError):
            return None
    
    def _parse_time(self, time_str: str) -> Optional[float]:
        """Parse UTC time from NMEA format"""
        if not time_str or len(time_str) < 6:
            return None
        
        try:
            hours = int(time_str[:2])
            minutes = int(time_str[2:4])
            seconds = float(time_str[4:])
            
            # Convert to timestamp (simplified - using current date)
            now = datetime.now(timezone.utc)
            time_today = now.replace(hour=hours, minute=minutes, second=int(seconds), microsecond=0)
            
            return time_today.timestamp()
            
        except (ValueError, IndexError):
            return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date from NMEA format (DDMMYY)"""
        if not date_str or len(date_str) != 6:
            return None
        
        try:
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = 2000 + int(date_str[4:6])
            
            return f"{year:04d}-{month:02d}-{day:02d}"
            
        except (ValueError, IndexError):
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get parser statistics"""
        total_sentences = self.sentences_parsed + self.sentences_failed
        success_rate = (self.sentences_parsed / total_sentences * 100) if total_sentences > 0 else 0
        
        return {
            "sentences_parsed": self.sentences_parsed,
            "sentences_failed": self.sentences_failed,
            "checksum_errors": self.checksum_errors,
            "success_rate": success_rate,
            "supported_types": list(self.sentence_handlers.keys())
        }


class GPSDataProcessor:
    """GPS data processor for combining multiple NMEA sentences"""
    
    def __init__(self):
        self.parser = NMEAParser()
        self.current_fix = None
        self.fix_history: List[GPSFix] = []
        self.max_history = 1000
        
        # Data accumulation
        self.partial_data: Dict[str, Any] = {}
        self.last_update_time = 0
        self.update_threshold = 1.0  # seconds
        
    def process_sentence(self, sentence: str) -> Optional[GPSFix]:
        """
        Process NMEA sentence and potentially return complete GPS fix
        
        Args:
            sentence: Raw NMEA sentence
            
        Returns:
            GPSFix object if complete fix is available, None otherwise
        """
        parsed_data = self.parser.parse_gps_data(sentence)
        if not parsed_data:
            return None
        
        # Accumulate data from different sentence types
        self._accumulate_data(parsed_data)
        
        # Check if we have enough data for a complete fix
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_threshold:
            fix = self._create_fix()
            if fix:
                self.current_fix = fix
                self.fix_history.append(fix)
                
                # Limit history size
                if len(self.fix_history) > self.max_history:
                    self.fix_history = self.fix_history[-self.max_history:]
                
                self.last_update_time = current_time
                return fix
        
        return None
    
    def _accumulate_data(self, data: Dict[str, Any]):
        """Accumulate data from different NMEA sentence types"""
        data_type = data.get('type')
        
        if data_type == 'GGA':
            self.partial_data.update({
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'altitude': data.get('altitude'),
                'satellites': data.get('satellites'),
                'hdop': data.get('hdop'),
                'fix_quality': data.get('fix_quality')
            })
        
        elif data_type == 'RMC':
            self.partial_data.update({
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'speed': data.get('speed_ms'),
                'course': data.get('course'),
                'status': data.get('status')
            })
        
        elif data_type == 'GSA':
            self.partial_data.update({
                'fix_type': data.get('fix_type'),
                'hdop': data.get('hdop'),
                'vdop': data.get('vdop')
            })
        
        elif data_type == 'VTG':
            self.partial_data.update({
                'speed': data.get('speed_ms'),
                'course': data.get('true_course')
            })
    
    def _create_fix(self) -> Optional[GPSFix]:
        """Create GPS fix from accumulated data"""
        # Check if we have minimum required data
        required_fields = ['latitude', 'longitude']
        if not all(field in self.partial_data for field in required_fields):
            return None
        
        # Determine fix quality
        fix_quality = self._determine_fix_quality()
        
        fix = GPSFix(
            timestamp=time.time(),
            latitude=self.partial_data.get('latitude', 0.0),
            longitude=self.partial_data.get('longitude', 0.0),
            altitude=self.partial_data.get('altitude', 0.0),
            speed=self.partial_data.get('speed', 0.0),
            course=self.partial_data.get('course', 0.0),
            satellites=self.partial_data.get('satellites', 0),
            hdop=self.partial_data.get('hdop', 99.9),
            vdop=self.partial_data.get('vdop', 99.9),
            fix_type=self.partial_data.get('fix_type', 1),
            fix_quality=fix_quality
        )
        
        return fix
    
    def _determine_fix_quality(self) -> str:
        """Determine GPS fix quality based on available data"""
        satellites = self.partial_data.get('satellites', 0)
        hdop = self.partial_data.get('hdop', 99.9)
        fix_type = self.partial_data.get('fix_type', 1)
        
        if fix_type >= 3 and satellites >= 8 and hdop <= 1.0:
            return "excellent"
        elif fix_type >= 3 and satellites >= 6 and hdop <= 2.0:
            return "good"
        elif fix_type >= 2 and satellites >= 4 and hdop <= 5.0:
            return "fair"
        else:
            return "poor"
    
    def get_current_fix(self) -> Optional[GPSFix]:
        """Get the most recent GPS fix"""
        return self.current_fix
    
    def get_fix_history(self, limit: int = 100) -> List[GPSFix]:
        """Get GPS fix history"""
        return self.fix_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processor statistics"""
        parser_stats = self.parser.get_statistics()
        
        fix_count = len(self.fix_history)
        avg_accuracy = 0.0
        avg_satellites = 0.0
        
        if fix_count > 0:
            recent_fixes = self.fix_history[-100:]  # Last 100 fixes
            avg_accuracy = sum(fix.hdop for fix in recent_fixes) / len(recent_fixes)
            avg_satellites = sum(fix.satellites for fix in recent_fixes) / len(recent_fixes)
        
        return {
            "parser": parser_stats,
            "total_fixes": fix_count,
            "current_fix_age": time.time() - self.current_fix.timestamp if self.current_fix else None,
            "average_accuracy": avg_accuracy,
            "average_satellites": avg_satellites,
            "fix_quality": self.current_fix.fix_quality if self.current_fix else "none"
        }
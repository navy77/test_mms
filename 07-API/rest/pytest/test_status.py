import pytest
from datetime import datetime, timedelta, timezone
import os
import sys

# Ensure parent directory is in path so we can import routers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.status import calculate_status_ratio, StatusSegment, TZ_BANGKOK

# ==============================================================================
# UNIT TESTS FOR STATUS CALCULATION RATIO
# ==============================================================================

def test_status_calculation_simple_sequence():
    # Case 1: Simple sequence (status_1 -> status_2)
    # Start: 10:00, End: 11:00 (Total 3600.0s)
    # 10:10: status_1
    # 10:30: status_2
    # Expect:
    #   no data: 10 mins (600.0s) -> 10:00-10:10
    #   status_1: 20 mins (1200.0s) -> 10:10-10:30
    #   status_2: 30 mins (1800.0s) -> 10:30-11:00
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK), "status": "status_1"},
        {"created_at": datetime(2026, 7, 7, 10, 30, 0, tzinfo=TZ_BANGKOK), "status": "status_2"}
    ]
    initial = None
    segments = calculate_status_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.status: seg for seg in segments}
    assert "no data" in seg_dict
    assert "status_1" in seg_dict
    assert "status_2" in seg_dict
    assert seg_dict["no data"].duration == 600.0
    assert seg_dict["status_1"].duration == 1200.0
    assert seg_dict["status_2"].duration == 1800.0

def test_status_calculation_with_initial_status():
    # Case 2: Status starts before start_time and changes inside
    # Start: 10:00, End: 11:00 (Total 3600.0s)
    # Initial: "status_1"
    # 10:20: status_2
    # Expect:
    #   status_1: 20 mins (1200.0s) -> 10:00-10:20
    #   status_2: 40 mins (2400.0s) -> 10:20-11:00
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK), "status": "status_2"}
    ]
    initial = {"status": "status_1", "created_at": datetime(2026, 7, 7, 9, 30, 0, tzinfo=TZ_BANGKOK)}
    segments = calculate_status_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.status: seg for seg in segments}
    assert "no data" not in seg_dict
    assert "status_1" in seg_dict
    assert "status_2" in seg_dict
    assert seg_dict["status_1"].duration == 1200.0
    assert seg_dict["status_2"].duration == 2400.0

def test_status_calculation_no_events_no_initial():
    # Case 3: No events and no initial status
    # Expect "no data" for the entire range
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = []
    initial = None
    segments = calculate_status_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.status: seg for seg in segments}
    assert "no data" in seg_dict
    assert seg_dict["no data"].duration == 3600.0
    assert seg_dict["no data"].ratio == 100.0

def test_status_calculation_no_events_with_initial():
    # Case 4: No events but initial status is present
    # Expect initial status for the entire range (3600s)
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = []
    initial = {"status": "status_1", "created_at": datetime(2026, 7, 7, 9, 30, 0, tzinfo=TZ_BANGKOK)}
    segments = calculate_status_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.status: seg for seg in segments}
    assert "status_1" in seg_dict
    assert seg_dict["status_1"].duration == 3600.0
    assert seg_dict["status_1"].ratio == 100.0

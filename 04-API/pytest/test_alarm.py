from datetime import datetime
import os
import sys

# Ensure parent directory is in path so we can import routers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.alarm import calculate_alarm_ratio, TZ_BANGKOK

# ==============================================================================
# UNIT TESTS FOR ALARM CALCULATION RATIO
# ==============================================================================

def test_alarm_calculation_simple_pair():
    # Case 1: Simple pair (alarm_1 starts, alarm_1_ ends)
    # Start: 10:00, End: 11:00
    # 10:10: alarm_1
    # 10:30: alarm_1_
    # Expect: 
    #   alarm_1: 20 mins (1200.0s) -> 10:10-10:30 (ratio 100.0%)
    #   normal/no data is not in results.
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK), "status": "alarm_1"},
        {"created_at": datetime(2026, 7, 7, 10, 30, 0, tzinfo=TZ_BANGKOK), "status": "alarm_1_"}
    ]
    initial = set()
    segments, final_active = calculate_alarm_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.alarm: seg for seg in segments}
    assert "normal" not in seg_dict
    assert "alarm_1" in seg_dict
    assert seg_dict["alarm_1"].duration == 1200.0
    assert seg_dict["alarm_1"].ratio == 100.0
    assert final_active == set()

def test_alarm_calculation_carry_in():
    # Case 2: Alarm starts before start_time and ends inside
    # Start: 10:00, End: 11:00
    # Initial: {"alarm_1"}
    # 10:20: alarm_1_
    # Expect:
    #   alarm_1: 20 mins (1200.0s) -> 10:00-10:20 (ratio 100.0%)
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK), "status": "alarm_1_"}
    ]
    initial = {"alarm_1"}
    segments, final_active = calculate_alarm_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.alarm: seg for seg in segments}
    assert "normal" not in seg_dict
    assert "alarm_1" in seg_dict
    assert seg_dict["alarm_1"].duration == 1200.0
    assert seg_dict["alarm_1"].ratio == 100.0
    assert final_active == set()

def test_alarm_calculation_overlapping():
    # Case 3: Overlapping alarms
    # Start: 10:00, End: 11:00
    # 10:10: alarm_1 starts
    # 10:20: alarm_2 starts (alarm_1 & alarm_2 active)
    # 10:40: alarm_1_ ends (alarm_2 active)
    # 10:50: alarm_2_ ends
    # Expect:
    #   alarm_1: 10 mins (10:10-10:20) + 20 mins (10:20-10:40) = 30 mins (1800.0s)
    #   alarm_2: 20 mins (10:20-10:40) + 10 mins (10:40-10:50) = 30 mins (1800.0s)
    #   ratio for both = 50.0%
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK), "status": "alarm_1"},
        {"created_at": datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK), "status": "alarm_2"},
        {"created_at": datetime(2026, 7, 7, 10, 40, 0, tzinfo=TZ_BANGKOK), "status": "alarm_1_"},
        {"created_at": datetime(2026, 7, 7, 10, 50, 0, tzinfo=TZ_BANGKOK), "status": "alarm_2_"}
    ]
    initial = set()
    segments, final_active = calculate_alarm_ratio(records, start_time, end_time, initial, "device_1")
    
    seg_dict = {seg.alarm: seg for seg in segments}
    assert "normal" not in seg_dict
    assert "alarm_1" in seg_dict
    assert "alarm_2" in seg_dict
    assert seg_dict["alarm_1"].duration == 1800.0
    assert seg_dict["alarm_2"].duration == 1800.0
    assert seg_dict["alarm_1"].ratio == 50.0
    assert seg_dict["alarm_2"].ratio == 50.0
    assert final_active == set()

def test_alarm_calculation_no_data():
    # Case 4: No data initial, no records at all
    # Expect empty segments list
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = []
    initial = {"no data"}
    segments, final_active = calculate_alarm_ratio(records, start_time, end_time, initial, "device_1")
    
    assert len(segments) == 0
    assert final_active == {"no data"}

def test_alarm_calculation_close_without_start():
    # Case 5: Close event received without initial start or preceding start event
    # Start: 07:00:00, End: 09:13:19
    # 08:40:00: alarm1_ (close event)
    # Expect: 
    #   alarm1: active from 07:00:00 to 08:40:00 = 6000.0s (100.0%)
    case5_start = datetime(2026, 7, 7, 7, 0, 0, tzinfo=TZ_BANGKOK)
    case5_end = datetime(2026, 7, 7, 9, 13, 19, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 8, 40, 0, tzinfo=TZ_BANGKOK), "status": "alarm1_"}
    ]
    initial = set()
    segments, final_active = calculate_alarm_ratio(records, case5_start, case5_end, initial, "device_1")
    
    seg_dict = {seg.alarm: seg for seg in segments}
    assert "alarm1" in seg_dict
    assert seg_dict["alarm1"].duration == 6000.0
    assert seg_dict["alarm1"].ratio == 100.0
    assert final_active == set()

def test_alarm_calculation_start_without_close():
    # Case 6: Alarm start event received but no end event before query end
    # Start: 07:00:00, End: 09:13:19
    # 08:40:00: alarm1 (start event)
    # Expect:
    #   alarm1: active from 08:40:00 to 09:13:19 = 1999.0s (100.0%)
    case6_start = datetime(2026, 7, 7, 7, 0, 0, tzinfo=TZ_BANGKOK)
    case6_end = datetime(2026, 7, 7, 9, 13, 19, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 8, 40, 0, tzinfo=TZ_BANGKOK), "status": "alarm1"}
    ]
    initial = set()
    segments, final_active = calculate_alarm_ratio(records, case6_start, case6_end, initial, "device_1")
    
    seg_dict = {seg.alarm: seg for seg in segments}
    assert "alarm1" in seg_dict
    assert seg_dict["alarm1"].duration == 1999.0
    assert seg_dict["alarm1"].ratio == 100.0
    assert final_active == {"alarm1"}

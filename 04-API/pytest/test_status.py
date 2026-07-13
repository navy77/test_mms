from datetime import datetime
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure parent directory is in path so we can import routers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.status import (
    TZ_BANGKOK,
    calculate_status_ratio,
    calculate_status_timeline,
    get_state_status_batch,
    resolve_devices,
)


class _QueryResult:
    def __init__(self, rows):
        self.result_rows = rows


class _RegisteredDevicesClient:
    def query(self, query, parameters):
        assert parameters == {"process": "demo1"}
        return _QueryResult([("no_1",), ("no_2",), ("no_3",)])


def test_resolve_devices_uses_requested_devices():
    devices = resolve_devices(_RegisteredDevicesClient(), "demo1", "no_2, no_1,no_2")

    assert devices == ["no_2", "no_1"]


@patch("routers.status.fetch_registered_devices", return_value=["no_1", "no_2", "no_3"])
def test_resolve_devices_uses_all_registered_devices_when_omitted(mock_fetch_devices):
    devices = resolve_devices(_RegisteredDevicesClient(), "demo1", None)

    assert devices == ["no_1", "no_2", "no_3"]
    mock_fetch_devices.assert_called_once_with("demo1")


@patch("routers.status.get_ch_client")
def test_state_batch_serializes_timeline_strings(mock_get_client):
    initial_result = MagicMock()
    initial_result.result_rows = [
        ("no_1", "run", datetime(2026, 7, 7, 6, 30, tzinfo=TZ_BANGKOK))
    ]
    timeline_result = MagicMock()
    timeline_result.result_rows = []
    mock_client = MagicMock()
    mock_client.query.side_effect = [initial_result, timeline_result]
    mock_get_client.return_value = mock_client

    response = get_state_status_batch("demo1", "no_1")

    assert response["no_1"][0]["status"] == "run"
    assert isinstance(response["no_1"][0]["start_time"], str)
    assert isinstance(response["no_1"][0]["end_time"], str)

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


# ==============================================================================
# UNIT TESTS FOR STATUS TIMELINE (NEW)
# ==============================================================================

def test_status_timeline_simple_sequence():
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK), "status": "status_1"},
        {"created_at": datetime(2026, 7, 7, 10, 30, 0, tzinfo=TZ_BANGKOK), "status": "status_2"},
        {"created_at": datetime(2026, 7, 7, 10, 45, 0, tzinfo=TZ_BANGKOK), "status": "status_2"} # duplicate status, should merge
    ]
    initial = None
    timeline = calculate_status_timeline(records, start_time, end_time, initial, "device_1")
    
    assert len(timeline) == 3
    assert timeline[0].status == "no data"
    assert timeline[0].start_time == start_time.isoformat()
    assert timeline[0].end_time == datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[0].duration == 600.0

    assert timeline[1].status == "status_1"
    assert timeline[1].start_time == datetime(2026, 7, 7, 10, 10, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[1].end_time == datetime(2026, 7, 7, 10, 30, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[1].duration == 1200.0

    assert timeline[2].status == "status_2"
    assert timeline[2].start_time == datetime(2026, 7, 7, 10, 30, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[2].end_time == end_time.isoformat()
    assert timeline[2].duration == 1800.0

def test_status_timeline_with_initial():
    start_time = datetime(2026, 7, 7, 10, 0, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 7, 11, 0, 0, tzinfo=TZ_BANGKOK)
    records = [
        {"created_at": datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK), "status": "status_2"}
    ]
    initial = {"status": "status_1", "created_at": datetime(2026, 7, 7, 9, 30, 0, tzinfo=TZ_BANGKOK)}
    timeline = calculate_status_timeline(records, start_time, end_time, initial, "device_1")
    
    assert len(timeline) == 2
    assert timeline[0].status == "status_1"
    assert timeline[0].start_time == start_time.isoformat()
    assert timeline[0].end_time == datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[0].duration == 1200.0

    assert timeline[1].status == "status_2"
    assert timeline[1].start_time == datetime(2026, 7, 7, 10, 20, 0, tzinfo=TZ_BANGKOK).isoformat()
    assert timeline[1].end_time == end_time.isoformat()
    assert timeline[1].duration == 2400.0


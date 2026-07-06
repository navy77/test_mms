import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, date

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# นำเข้าตัวแปรแอป FastAPI
from main import app
# นำเข้า Helper ต่างๆ มาทดสอบการคำนวณวันทำงานแยกต่างหาก
from routers.data import get_production_day_range, TZ_BANGKOK

client = TestClient(app)

# ==========================================
# 1. UNIT TEST FOR PRODUCTION DAY BOUNDARY
# ==========================================
def test_production_day_boundary_after_seven():
    # เคสเวลาหลัง 07:00 น. -> วันผลิตต้องเป็นวันเดียวกัน
    test_dt = datetime(2026, 7, 6, 14, 30, 0, tzinfo=TZ_BANGKOK)
    start_time, end_time = get_production_day_range(test_dt)
    
    assert start_time.date() == date(2026, 7, 6)
    assert start_time.hour == 7
    assert end_time.date() == date(2026, 7, 7)
    assert end_time.hour == 6

def test_production_day_boundary_before_seven():
    # เคสเวลาช่วงเช้ามืดก่อน 07:00 น. -> วันผลิตต้องเป็นของเมื่อวาน
    test_dt = datetime(2026, 7, 6, 5, 0, 0, tzinfo=TZ_BANGKOK)
    start_time, end_time = get_production_day_range(test_dt)
    
    assert start_time.date() == date(2026, 7, 5)
    assert start_time.hour == 7
    assert end_time.date() == date(2026, 7, 6)
    assert end_time.hour == 6


# ==========================================
# 2. INTEGRATION TEST FOR API ENDPOINTS (MOCKED CH)
# ==========================================
@patch('routers.data.get_ch_client')
def test_get_hourly_process_success(mock_get_client):
    # Mock Clickhouse database client
    mock_db = MagicMock()
    mock_result = MagicMock()
    # จำลองคอลัมน์และแถวที่ถูกส่งกลับจาก DB
    mock_result.column_names = ["process", "device", "data1", "created_at"]
    mock_result.result_rows = [
        ["demo1", "no_1", 10.5, datetime(2026, 7, 6, 14, 0, 0)]
    ]
    mock_db.query.return_value = mock_result
    mock_get_client.return_value = mock_db

    # เรียกยิง API จริง
    response = client.get("/api/v1/data/hourly/demo1")
    
    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data) == 1
    assert json_data[0]["device"] == "no_1"
    assert json_data[0]["data"][0]["data1"] == 10.5

@patch('routers.data.get_ch_client')
def test_get_hourly_process_not_found(mock_get_client):
    # จำลองว่าไม่มีข้อมูลใดๆ ใน Clickhouse เลย
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = []
    mock_db.query.return_value = mock_result
    mock_get_client.return_value = mock_db

    response = client.get("/api/v1/data/hourly/non_existent_process")
    assert response.status_code == 400
    assert response.json()["detail"] == "Item not found"

def test_get_monthly_invalid_params():
    # ส่งตัวแปรผิดรูปแบบ (เดือน 13)
    response = client.get("/api/v1/data/monthly/2026/13/demo1")
    assert response.status_code == 422  # Validation Error จาก FastAPI

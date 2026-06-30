"""
test_main_patient_endpoints.py — Test cho 4 endpoint mới
(/patient/save, /patient/{so_benh_an}, /patient, /patient/update) qua ĐÚNG
TẦNG HTTP (FastAPI TestClient), không chỉ gọi database.py trực tiếp — đúng
bài học đã rút ra trong dự án: test qua endpoint thật bắt được lỗi tích hợp
(field bị bỏ sót khi build response, sai thứ tự gọi...) mà test đơn vị
không bắt được.

Dùng file SQLite local tạm thời (không phải Turso thật) — giống cách
test_database.py đã làm, để CI không cần token Turso/kết nối mạng.
"""
import sys
import os
import json
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import pytest
from fastapi.testclient import TestClient

import main
import database as db


@pytest.fixture
def temp_db(monkeypatch):
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "test.db")
    monkeypatch.setattr(db, "_get_db_url", lambda: "file:" + tmp_path)
    monkeypatch.setattr(db, "_get_auth_token", lambda: None)
    db.init_db()
    yield
    try:
        os.remove(tmp_path)
    except OSError:
        pass


@pytest.fixture
def client(temp_db):
    return TestClient(main.app)


@pytest.fixture
def mock_anthropic_patient_update():
    """Mock riêng cho test update: Bước 1 (extraction) trả report_moi nhỏ —
    không cần đầy đủ như mock_anthropic chính trong test_main.py vì chỉ cần
    test luồng gộp dữ liệu, không cần test chất lượng narrative."""
    fake_new_report = {
        "xet_nghiem_key": [{"key": "INR", "rawVal": 2.8, "trend": [2.4, 2.8], "ngay": "15/06/2026"}],
        "thuoc_cuoi_ky": [{"ten_thuoc": "Sintrom 4mg (liều mới)"}],
    }

    def _side_effect(*args, **kwargs):
        return json.dumps(fake_new_report, ensure_ascii=False)

    with patch("main.call_claude", side_effect=_side_effect):
        yield


def _sample_report(so_benh_an="02.000001", **overrides):
    base = {
        "thong_tin_benh_nhan": {"ho_ten": "Bệnh Nhân Test", "tuoi": 65, "gioi_tinh": "Nữ", "so_benh_an": so_benh_an},
        "chan_doan_chinh": "Rung nhĩ, tăng huyết áp",
        "xet_nghiem_key": [{"key": "INR", "rawVal": 2.4, "trend": [2.4], "ngay": "01/01/2026"}],
        "thuoc_cuoi_ky": [{"ten_thuoc": "Sintrom 4mg"}],
    }
    base.update(overrides)
    return base


# ─── POST /patient/save ───────────────────────────────────────────────────
def test_save_patient_thanh_cong(client):
    resp = client.post("/patient/save", json={"report": _sample_report()})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["so_benh_an"] == "02.000001"


def test_save_patient_trung_so_benh_an_tra_409(client):
    client.post("/patient/save", json={"report": _sample_report()})
    resp2 = client.post("/patient/save", json={"report": _sample_report()})
    assert resp2.status_code == 409


# ─── GET /patient/{so_benh_an} ────────────────────────────────────────────
def test_get_patient_chua_luu_tra_404(client):
    resp = client.get("/patient/00.999999")
    assert resp.status_code == 404


def test_get_patient_tra_dung_report_va_tinh_lai_analysis(client):
    client.post("/patient/save", json={"report": _sample_report()})
    resp = client.get("/patient/02.000001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["report"]["thong_tin_benh_nhan"]["ho_ten"] == "Bệnh Nhân Test"
    assert "analysis" in data
    assert "active_profiles" in data["analysis"]
    profile_ids = [p["profile_id"] for p in data["analysis"]["active_profiles"]]
    assert "atrial_fibrillation" in profile_ids


# ─── GET /patient (danh sách) ──────────────────────────────────────────────
def test_list_patients_rong_khi_chua_co_ho_so(client):
    resp = client.get("/patient")
    assert resp.status_code == 200
    assert resp.json()["patients"] == []


def test_list_patients_tra_dung_ho_so_da_luu(client):
    client.post("/patient/save", json={"report": _sample_report(so_benh_an="02.000001")})
    client.post("/patient/save", json={"report": _sample_report(so_benh_an="02.000002")})
    resp = client.get("/patient")
    data = resp.json()
    assert len(data["patients"]) == 2


# ─── POST /patient/update — tính năng "cập nhật theo thời gian thực" ──────
def test_update_patient_chua_co_ho_so_tra_404(client):
    resp = client.post("/patient/update", json={
        "so_benh_an": "00.999999",
        "ho_so_text": "noi dung tai lieu dai it nhat vai chuc ky tu de qua kiem tra",
    })
    assert resp.status_code == 404


def test_update_patient_thanh_cong_gop_dung_du_lieu(client, mock_anthropic_patient_update):
    client.post("/patient/save", json={"report": _sample_report()})
    resp = client.post("/patient/update", json={
        "so_benh_an": "02.000001",
        "ho_so_text": "noi dung tai lieu tai kham moi dai it nhat vai chuc ky tu de qua kiem tra do dai",
        "nguon_tai_lieu": "tai_kham_2.pdf",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["so_lan_cap_nhat"] == 2
    inr_values = [x["rawVal"] for x in data["report"]["xet_nghiem_key"] if x["key"] == "INR"]
    assert 2.4 in inr_values
    assert 2.8 in inr_values
    assert "analysis" in data
    assert "active_profiles" in data["analysis"]


def test_update_patient_loi_json_tra_loi_ro(client):
    """Nếu Claude trả về text không parse được JSON, phải báo lỗi rõ ràng
    (status 200, success=False) — KHÔNG crash 500."""
    client.post("/patient/save", json={"report": _sample_report()})
    with patch("main.call_claude") as mock_call:
        mock_call.return_value = "đây không phải JSON hợp lệ chút nào"
        resp = client.post("/patient/update", json={
            "so_benh_an": "02.000001",
            "ho_so_text": "noi dung tai lieu dai it nhat vai chuc ky tu de qua kiem tra do dai toi thieu",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

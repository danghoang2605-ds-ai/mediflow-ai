# MedParcours AI

Trợ lý AI phân tích hồ sơ bệnh án cho bác sĩ Việt Nam — đọc PDF/Word/Excel/
PowerPoint xuất từ HIS, tự động tổng hợp diễn biến lâm sàng, phát hiện cảnh báo
nguy cơ, tính thang điểm CHA2DS2-VASc/HAS-BLED, theo dõi TTR chống đông, và
trợ lý hỏi-đáp MedAmi theo từng hồ sơ cụ thể.

**HackAIthon 2026 — Bảng B Challenger, Đề tài 5: Y tế — Team UN1SVENGERS**

> Mọi cảnh báo/điểm số là **hỗ trợ quyết định**, không tự chẩn đoán hoặc kê
> đơn. Luôn cần bác sĩ xác nhận trước khi áp dụng vào điều trị thật.

---

## Cài đặt 1 lệnh (Docker)

**Yêu cầu:** Docker + Docker Compose đã cài sẵn.

```bash
# 1. Tạo file .env từ mẫu, điền ANTHROPIC_API_KEY thật
cp .env.example .env
# (Mở .env, sửa ANTHROPIC_API_KEY=sk-ant-...)

# 2. Chạy
docker-compose up --build
```

Sau khi build xong (lần đầu mất vài phút để cài dependency):
- **Frontend:** http://localhost:8080
- **Backend API:** http://localhost:8000 (xem `/docs` cho danh sách endpoint)

Đăng nhập demo: `hackaithon2026` / `medparcours`

Dừng: `docker-compose down`

### Kiến trúc Docker (chỉ gồm backend + frontend)

```
docker-compose.yml
  ├─ backend   (Dockerfile.backend)  — FastAPI + rule engine, cổng 8000
  └─ frontend  (Dockerfile.frontend) — App.jsx build bằng esbuild, nginx, cổng 8080
```

Không có service `db` — bản demo này dùng kiến trúc "Pilot/Demo" (xem
`medparcours_roadmap_v2.md` mục 3.4), không lưu trữ lịch sử lâu dài. Giai đoạn
thương mại hóa thật (on-premise, có Postgres) sẽ thêm sau, ngoài phạm vi demo
Vòng 2 này.

---

## Chạy không cần Docker (dev nhanh)

**Backend:**
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8000
```

**Frontend:** mở `App.jsx` qua môi trường React có sẵn (claude.ai artifact,
hoặc tự dựng entry point như `docker_setup/mount.jsx`), hoặc dùng trực tiếp
bản đã deploy GitHub Pages.

---

## Script test tự động (pytest)

```bash
pip install -r requirements-dev.txt
pytest test_main.py -v
```

16 test, mock Anthropic API (không tốn token thật, không cần mạng):
- `/health`, `/analyze_text`, `/analyze` (PDF/Word/Excel/PowerPoint), `/chat`,
  `/ecg`, `/ecg/synthetic`
- Thang điểm CHA2DS2-VASc/HAS-BLED, TTR, care-gap detector, trùng nhóm thuốc
- Hồi quy: câu phủ định ("không ghi nhận đái tháo đường") không bị tính nhầm
  thành dương tính — lỗi thật đã phát hiện và sửa trong quá trình phát triển
- Idempotent: chạy 3 lần liên tiếp không lỗi
- File hỏng/sai định dạng trả lỗi rõ nghĩa, không crash 500

---

## Cấu trúc thư mục

```
.
├── App.jsx                    # Frontend — React single-file, ~6500 dòng
├── main.py                    # Backend — FastAPI, pipeline 3 bước (LLM → rule engine → LLM)
├── clinical_rules.py          # Rule engine tất định — KHÔNG qua LLM (an toàn-tính mạng)
├── ecg_engine.py              # Số hóa ảnh ECG (Mức 1: trích tín hiệu)
├── document_extract.py        # Trích text từ Word/Excel/PowerPoint
├── test_main.py                # Script test pytest
├── requirements.txt            # Dependency production
├── requirements-dev.txt        # + pytest, httpx (chỉ cho test)
├── docker-compose.yml
├── docker_setup/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── mount.jsx               # Entry point React (createRoot) cho bản Docker
│   └── index.html
├── .env.example
└── medparcours_roadmap_v2.md   # Kế hoạch kỹ thuật + business chi tiết
```

### Kiến trúc pipeline backend (3 bước hybrid)

```
PDF/Word/Excel/PowerPoint
        │
        ▼
  Trích text (pypdf / python-docx / openpyxl / python-pptx)
        │
        ▼
  Bước 1 (LLM): Claude đọc → JSON có cấu trúc (KHÔNG đánh giá)
        │
        ▼
  Bước 2 (Rule Engine Python, clinical_rules.py): TẤT ĐỊNH, không LLM
    - eGFR (CKD-EPI 2021), an toàn thuốc, CHA2DS2-VASc/HAS-BLED, TTR, care-gaps
        │
        ▼
  Bước 3 (LLM): Claude diễn đạt xu hướng (CHỈ từ delta rule engine, không bịa)
        │
        ▼
  Báo cáo có cấu trúc → Frontend (App.jsx)
```

**Nguyên tắc cốt lõi:** mọi logic an toàn-tính mạng (eGFR, ngưỡng INR, thang
điểm nguy cơ, tương tác thuốc) nằm trong rule engine Python tất định —
KHÔNG bao giờ để LLM tự suy luận các con số này.

---

## Triển khai thật (không phải demo)

- **Frontend:** GitHub Pages (xem `ASSET_BASE` trong App.jsx tự tính theo path deploy)
- **Backend:** Hugging Face Spaces (Docker) — xem Space để biết URL hiện tại

Đổi `window.MEDIFLOW_API_URL` trong `index.html` nếu backend đổi URL, không
cần sửa `App.jsx`.

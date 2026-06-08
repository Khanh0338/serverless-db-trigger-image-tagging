# 🖼️ Serverless DB Trigger: Automatic Image Tagging (Project #123)

## 📌 Giới thiệu

Dự án triển khai hệ thống **Gắn thẻ ảnh tự động (Automatic Image Tagging)** sử dụng mô hình **Serverless Function** (mô phỏng AWS Lambda) trong môi trường **cơ sở dữ liệu phân tán** với **2 site**:

- **Site A**: Bảng `Image_Metadata` — nơi **nhận và lưu ảnh gốc** (ID, URL, Tags=NULL)
- **Site B**: Bảng `Image_Metadata` — nơi **lưu trữ đồng bộ** kèm Tag sau khi AI xử lý

## 🧠 Vấn đề chính giải quyết

- **Serverless Trigger**: Khi một dòng được INSERT vào Site A, hàm Lambda tự động được kích hoạt để gắn tag và đồng bộ sang Site B.
- **Cold Start Latency**: Phân tích độ trễ khởi động lạnh (Cold Start) của Serverless Function — lần đầu tiên container chưa được khởi tạo sẽ mất thêm ~1.5 giây so với các lần "ấm" tiếp theo.
- **Benchmark theo Volume**: Đo lường thời gian thực thi trung bình của trigger so với số lượng ảnh đầu vào (1, 5, 20, 50 ảnh).

## 🔧 Công nghệ sử dụng

- **Ngôn ngữ**: Python 3
- **Cơ sở dữ liệu phân tán**: MySQL (2 database: `site_a_db`, `site_b_db`)
- **Thư viện chính**: `mysql-connector-python`
- **Mô phỏng Serverless**: Hàm `serverless_trigger_handler()` — giả lập AWS Lambda với Cold Start (1.5s) và Warm execution (~0.05s)
- **AI Tagging**: Hàm `mock_ai_tagging_api()` — phân tích URL để tự động gán nhãn (cat, dog, ocean, mountain, v.v.)

## ⚙️ Cài đặt và Chạy dự án

### Yêu cầu hệ thống

- Python 3.8+
- MySQL Server (đang chạy)

### Hướng dẫn cài đặt

1. Clone repository (hoặc tải zip): `git clone <repo-url>`
2. Cài đặt thư viện: `pip install mysql-connector-python`
3. Mở file `serverless_image_tagging.py`, sửa thông tin kết nối MySQL trong biến `MYSQL_CONFIG`:
   ```python
   MYSQL_CONFIG = { 'host': 'localhost', 'user': 'root', 'password': 'your_password' }
   ```

## 🚀 Hướng dẫn sử dụng

1. Chạy chương trình: `python serverless_image_tagging.py`
2. Chương trình sẽ tự động:
   - Khởi tạo 2 database (`site_a_db`, `site_b_db`) với bảng `Image_Metadata`
   - Chạy benchmark theo 4 mức volume: **1, 5, 20, 50 ảnh**
   - In bảng kết quả so sánh tổng thời gian và thời gian trung bình/ảnh
   - In chi tiết gói 5 ảnh để làm nổi bật hiệu ứng **Cold Start vs Warm**

## 📊 Phân tích Cold Start Latency# 🖼️ Serverless DB Trigger: Automatic Image Tagging (Project #123)

## 📌 Giới thiệu

Dự án triển khai hệ thống **Gắn thẻ ảnh tự động (Automatic Image Tagging)** sử dụng mô hình **Serverless Function** (mô phỏng AWS Lambda) trong môi trường **cơ sở dữ liệu phân tán** với **2 site**:

- **Site A** (`site_a_db`): Bảng `Image_Metadata` — nơi **nhận và lưu ảnh gốc** (ID, URL, Tags = NULL)
- **Site B** (`site_b_db`): Bảng `Image_Metadata` — nơi **lưu trữ đồng bộ** kèm Tag sau khi AI xử lý; kèm bảng `Dead_Letter_Queue` để ghi lại các lỗi đồng bộ

## 🧠 Vấn đề chính giải quyết

- **Serverless Trigger**: Khi một dòng được INSERT vào Site A, hàm Lambda tự động được kích hoạt để gắn tag và đồng bộ sang Site B.
- **Cold Start Latency**: Phân tích độ trễ khởi động lạnh — lần đầu tiên container chưa được khởi tạo sẽ mất thêm ~1.5 giây so với các lần "ấm" tiếp theo.
- **Dead Letter Queue (DLQ)**: Các lỗi đồng bộ (mất kết nối, Site B sập...) được ghi lại vào bảng `Dead_Letter_Queue` tại Site B để phục hồi sau.
- **Benchmark theo Volume**: Đo lường thời gian thực thi trung bình của trigger với 1, 5, 20, 50 ảnh.

## 🔧 Công nghệ sử dụng

| Thành phần | Chi tiết |
|---|---|
| Ngôn ngữ | Python 3.11 |
| Cơ sở dữ liệu | MySQL 8.0 (2 container: `site_a`, `site_b`) |
| Thư viện | `mysql-connector-python==9.0.0` |
| Môi trường chạy | Docker Compose |
| Mô phỏng Serverless | Hàm `serverless_trigger_handler()` — Cold Start 1.5s, Warm ~0.05s |
| AI Tagging | Hàm `mock_ai_tagging_api()` — phân tích URL để tự động gán nhãn |

## 🗂️ Cấu trúc dự án

```
.
├── docker-compose.yml      # Định nghĩa 3 service: site_a, site_b, app
├── Dockerfile              # Build image cho service app (Python 3.11-slim)
├── requirements.txt        # mysql-connector-python==9.0.0
├── main.py                 # Code chính của hệ thống
└── output/                 # Thư mục nhận file báo cáo benchmark (volume mount)
    └── benchmark_report.txt
```

## ⚙️ Cài đặt và chạy dự án

### Yêu cầu hệ thống

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (bao gồm Docker Compose)

### Các bước chạy

**1. Clone repository (hoặc tải zip):**
```bash
git clone <repo-url>
cd <tên-thư-mục>
```

**2. Tạo thư mục output (nếu chưa có):**
```bash
mkdir output
```

**3. Khởi động toàn bộ hệ thống:**
```bash
docker compose up --build
```

Docker Compose sẽ tự động:
- Khởi động container MySQL cho **Site A** (port `3307`) và **Site B** (port `3308`)
- Chờ cả hai database healthy (healthcheck tự động)
- Build và chạy container **app** (Python), kết nối vào cùng `db_network`

**4. Tương tác với chương trình:**

Sau khi các container khởi động, terminal sẽ hiển thị menu tương tác:

```
============================================================
  SERVERLESS DB TRIGGER — AUTOMATIC IMAGE TAGGING
  Dương Quốc Khánh | N23DCCN097
============================================================
  [1] Benchmark: Thời gian xử lý vs Volume dữ liệu
  [2] Demo các lỗi hệ thống phân tán
  [0] Thoát
------------------------------------------------------------
  Chọn:
```

**5. Dừng hệ thống:**
```bash
docker compose down
```

> **Lưu ý:** File báo cáo benchmark sẽ được xuất ra `./output/benchmark_report.txt` sau khi chọn chức năng `[1]`.

## 🚀 Hướng dẫn sử dụng

### Chức năng [1] — Benchmark

Đo lường thời gian xử lý theo 4 mức volume: **1, 5, 20, 50 ảnh**.  
Kết quả in ra terminal và xuất file `output/benchmark_report.txt`.

### Chức năng [2] — Demo lỗi phân tán

| Lựa chọn | Kịch bản |
|---|---|
| [1] | Site B ngừng hoạt động (bảng đích bị DROP) |
| [2] | Duplicate Trigger (INSERT trùng lặp ID) |
| [3] | Partial Failure (mất kết nối cục bộ) |
| [4] | Cold Start vượt ngưỡng SLA (0.5s) |
| [5] | Dữ liệu không nhất quán (URL không có từ khóa nhận diện) |
| [6] | Chạy tuần tự tất cả 5 lỗi |

## 📊 Phân tích Cold Start Latency

| Lần gọi | Trạng thái Container | Thời gian xử lý (ước tính) |
|---|---|---|
| Lần đầu tiên | ❄️ Cold | ~1.55s (1.5s init + 0.05s AI) |
| Các lần tiếp theo | 🔥 Warm | ~0.05s (chỉ AI tagging) |

> **Nhận xét**: Với volume lớn (50 ảnh), ảnh hưởng của Cold Start bị "pha loãng", thời gian trung bình/ảnh tiệm cận ~0.05s. Với volume nhỏ (1 ảnh), Cold Start chiếm phần lớn tổng thời gian.

## 📈 Kết quả Benchmark mẫu

```
Volume (Số ảnh) Tổng thời gian (s)     Thời gian TB / Ảnh (s) 
------------------------------------------------------------
1               1.5512                 1.5512                 
5               1.7521                 0.3504                 
20              2.5498                 0.1275                 
50              4.0510                 0.0810                 
```

## 🌐 Kiến trúc Docker Compose

```
┌─────────────────────────────────────────────┐
│               db_network (bridge)            │
│                                             │
│  ┌──────────────┐    ┌──────────────┐       │
│  │   site_a     │    │   site_b     │       │
│  │  MySQL 8.0   │    │  MySQL 8.0   │       │
│  │  port: 3307  │    │  port: 3308  │       │
│  └──────┬───────┘    └──────┬───────┘       │
│         │                   │               │
│         └────────┬──────────┘               │
│                  │                          │
│         ┌────────▼────────┐                 │
│         │  serverless_app │                 │
│         │  Python 3.11    │                 │
│         │  main.py        │                 │
│         └────────┬────────┘                 │
└──────────────────┼──────────────────────────┘
                   │ volume mount
              ./output/
```

## 🎬 Video demo

Xem video minh họa các lỗi tại đây: https://drive.google.com/drive/folders/1XOcaWvoDh60lbwbHLWfnq8HLQ9WDOdvj?usp=sharing

## 👥 Tác giả

- **Họ tên**: Dương Quốc Khánh
- **Mã số sinh viên**: N23DCCN097

## 📄 Giấy phép

MIT License


| Lần gọi         | Trạng thái Container | Thời gian xử lý (ước tính) |
|-----------------|----------------------|----------------------------|
| Lần đầu tiên    | ❄️ Cold (Lạnh)       | ~1.55s (1.5s init + 0.05s AI) |
| Các lần tiếp theo | 🔥 Warm (Ấm)       | ~0.05s (chỉ AI tagging)    |

> **Nhận xét**: Với volume lớn (50 ảnh), ảnh hưởng của Cold Start bị "pha loãng", thời gian trung bình/ảnh tiệm cận về ~0.05s. Với volume nhỏ (1 ảnh), Cold Start chiếm phần lớn tổng thời gian.

## 📈 Kết quả Benchmark mẫu

```
======================================================================
BẮT ĐẦU ĐO LƯỜNG: THỜI GIAN XỬ LÝ VS SỐ LƯỢNG DỮ LIỆU ĐẦU VÀO
======================================================================
Volume (Số ảnh)     Tổng thời gian (s)       Thời gian TB / Ảnh (s)  
----------------------------------------------------------------------
1                   1.5512                   1.5512                   
5                   1.7521                   0.3504                   
   👉 Chi tiết gói 5 ảnh: Lần 1 (Cold): 1.551s | Các lần sau (Warm): [0.051, 0.050, 0.051, 0.050]
20                  2.5498                   0.1275                   
50                  4.0510                   0.0810                   
```

## Video demo
Xem video minh họa các lỗi tại đây :https://drive.google.com/drive/folders/1XOcaWvoDh60lbwbHLWfnq8HLQ9WDOdvj?usp=sharing


## 👥 Tác giả

- **Họ tên**: Dương Quốc Khánh
- **Mã số sinh viên**: N23DCCN097

## 📄 Giấy phép

MIT License

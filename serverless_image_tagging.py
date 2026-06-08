import mysql.connector
import time
import random

# ================================
# CẤU HÌNH KẾT NỐI MYSQL
# ================================
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',  # Thay bằng mật khẩu của bạn
}

# ================================
# 1. KHỞI TẠO CƠ SỞ DỮ LIỆU (SITE A & SITE B)
# ================================
def init_databases():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS site_a_db")
    cursor.execute("CREATE DATABASE IF NOT EXISTS site_b_db")
    conn.close()

    # --- Site A: Nơi nhận ảnh gốc ---
    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()
    cursor_a.execute("""
        CREATE TABLE IF NOT EXISTS Image_Metadata (
            id INT AUTO_INCREMENT PRIMARY KEY,
            url VARCHAR(255),
            tags VARCHAR(255) DEFAULT NULL
        )
    """)
    cursor_a.execute("TRUNCATE TABLE Image_Metadata")
    conn_a.commit()
    conn_a.close()

    # --- Site B: Nơi lưu trữ đồng bộ kèm Tag ---
    conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
    cursor_b = conn_b.cursor()
    cursor_b.execute("""
        CREATE TABLE IF NOT EXISTS Image_Metadata (
            id INT PRIMARY KEY,
            url VARCHAR(255),
            tags VARCHAR(255)
        )
    """)
    cursor_b.execute("TRUNCATE TABLE Image_Metadata")
    conn_b.commit()
    conn_b.close()
    print("[DB] Đã khởi tạo cấu trúc dữ liệu trống cho Site A và Site B.")

# ================================
# 2. GIẢ LẬP SERVERLESS FUNCTION (AWS LAMBDA)
# ================================
IS_CONTAINER_WARM = False

def reset_serverless_container():
    global IS_CONTAINER_WARM
    IS_CONTAINER_WARM = False

def mock_ai_tagging_api(url):
    """Giả lập API AI quét từ khóa trong URL để gắn thẻ (mất 0.05s)"""
    time.sleep(0.05)
    url_lower = url.lower()
    tags = []
    if 'cat' in url_lower or 'kitty' in url_lower: tags.extend(['animal', 'cat', 'pet'])
    if 'dog' in url_lower or 'puppy' in url_lower: tags.extend(['animal', 'dog', 'pet'])
    if 'ocean' in url_lower or 'beach' in url_lower: tags.extend(['nature', 'sea', 'water'])
    if 'mountain' in url_lower: tags.extend(['nature', 'land', 'mountain'])
    return ", ".join(tags) if tags else "general, uncategorized"

def serverless_trigger_handler(image_id, url):
    """Hàm đại diện cho AWS Lambda Function."""
    global IS_CONTAINER_WARM
    start_time = time.time()

    if not IS_CONTAINER_WARM:
        time.sleep(1.5)
        IS_CONTAINER_WARM = True

    computed_tags = mock_ai_tagging_api(url)

    try:
        conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
        cursor_b = conn_b.cursor()
        cursor_b.execute(
            "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
            (image_id, url, computed_tags)
        )
        conn_b.commit()
        conn_b.close()
    except mysql.connector.Error as err:
        print(f"1 Lỗi đồng bộ Site B: {err}")

    return time.time() - start_time

# ================================
# 3. CHÈN DỮ LIỆU VÀO SITE A
# ================================
def insert_to_site_a_and_trigger(url_list):
    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()
    durations = []

    for url in url_list:
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        inserted_id = cursor_a.lastrowid
        elapsed = serverless_trigger_handler(inserted_id, url)
        durations.append(elapsed)

    conn_a.close()
    return durations

# ================================
# 4. BENCHMARK (OPTION 1)
# ================================
def run_benchmark():
    print("\n" + "="*70)
    print("BẮT ĐẦU ĐO LƯỜNG: THỜI GIAN XỬ LÝ VS SỐ LƯỢNG DỮ LIỆU ĐẦU VÀO")
    print("="*70)

    test_volumes = [1, 5, 20, 50]

    def generate_mock_urls(count):
        samples = [
            "https://example.com/images/cute_cat.jpg",
            "https://example.com/images/blue_ocean.png",
            "https://example.com/images/rocky_mountain.jpg",
            "https://example.com/images/happy_dog.jpeg"
        ]
        return [samples[i % len(samples)] for i in range(count)]

    print(f"{'Volume (Số ảnh)':<20}{'Tổng thời gian (s)':<25}{'Thời gian TB / Ảnh (s)':<25}")
    print("-" * 70)

    for volume in test_volumes:
        init_databases()
        reset_serverless_container()
        urls = generate_mock_urls(volume)
        durations = insert_to_site_a_and_trigger(urls)
        total_time = sum(durations)
        avg_time = total_time / volume
        print(f"{volume:<20}{total_time:<25.4f}{avg_time:<25.4f}")
        if volume == 5:
            print(f"   👉 Chi tiết gói 5 ảnh: Lần 1 (Cold): {durations[0]:.3f}s | Các lần sau (Warm): {[round(d,3) for d in durations[1:]]}")

# ================================
# 5. DEMO CÁC LỖI PHÂN TÁN (OPTION 2)
# ================================

def separator(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

# --------------------------------------------------
# LỖI 1: Site B ngừng hoạt động (giả lập DROP TABLE)
# --------------------------------------------------
def demo_loi_1_site_b_chet():
    separator("LỖI 1: Site B (Image_Metadata) ngừng hoạt động")
    print("► Mô tả: Site B bị 'chết' — bảng Image_Metadata bị xóa.")
    print("         Trigger cố đồng bộ nhưng bảng đích không tồn tại.")

    init_databases()
    reset_serverless_container()

    # Giả lập Site B chết bằng cách DROP bảng
    conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
    cursor_b = conn_b.cursor()
    cursor_b.execute("DROP TABLE IF EXISTS Image_Metadata")
    conn_b.commit()
    conn_b.close()
    print("\n  [SIM] Đã DROP bảng Image_Metadata tại Site B (giả lập Site B chết).")

    url = "https://example.com/images/cute_cat.jpg"
    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()
    cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
    conn_a.commit()
    inserted_id = cursor_a.lastrowid
    conn_a.close()

    print(f"  [Site A] INSERT thành công: id={inserted_id}, url={url}")
    print("  [Lambda] Trigger kích hoạt → cố gắng đồng bộ sang Site B...")

    try:
        conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
        cursor_b = conn_b.cursor()
        tags = mock_ai_tagging_api(url)
        cursor_b.execute(
            "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
            (inserted_id, url, tags)
        )
        conn_b.commit()
        conn_b.close()
        print("  [Site B] Đồng bộ thành công.")
    except mysql.connector.Error as err:
        print(f"\n  ❌ KẾT QUẢ: Đồng bộ THẤT BẠI — {err}")
        print("  ⚠️  Hậu quả: Site A có dữ liệu, Site B KHÔNG có → mất đồng nhất!")
        print("  💡 Giải pháp thực tế: Dead Letter Queue (DLQ) + Retry với Exponential Backoff.")

# --------------------------------------------------
# LỖI 2: Duplicate Trigger — INSERT trùng ID vào Site B
# --------------------------------------------------
def demo_loi_2_duplicate_trigger():
    separator("LỖI 2: Duplicate Trigger — INSERT trùng ID")
    print("► Mô tả: Lambda bị gọi 2 lần cho cùng 1 ảnh (at-least-once delivery).")
    print("         Lần 2 cố INSERT cùng id vào Site B → PRIMARY KEY conflict.")

    init_databases()
    reset_serverless_container()

    url = "https://example.com/images/blue_ocean.png"
    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()
    cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
    conn_a.commit()
    inserted_id = cursor_a.lastrowid
    conn_a.close()

    tags = mock_ai_tagging_api(url)

    for attempt in range(1, 3):
        print(f"\n  [Lambda] Lần gọi #{attempt} cho id={inserted_id}...")
        try:
            conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
            cursor_b = conn_b.cursor()
            cursor_b.execute(
                "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
                (inserted_id, url, tags)
            )
            conn_b.commit()
            conn_b.close()
            print(f"  ✅ Lần #{attempt}: INSERT thành công vào Site B.")
        except mysql.connector.Error as err:
            print(f"  ❌ Lần #{attempt}: THẤT BẠI — {err}")
            print("  💡 Giải pháp: Dùng INSERT IGNORE hoặc ON DUPLICATE KEY UPDATE để idempotent.")

# --------------------------------------------------
# LỖI 3: Partial Failure — ông
# --------------------------------------------------
def demo_loi_3_partial_failure():
    separator("LỖI 3: Partial Failure — đồng bộ một phần")
    print("► Mô tả: Batch 5 ảnh được INSERT vào Site A.")
    print("         Giữa chừng Site B bị lỗi ngẫu nhiên (30% xác suất thất bại).")
    print("         Kết quả: Site A đủ 5 record, Site B chỉ có một phần.\n")

    init_databases()
    reset_serverless_container()

    urls = [
        "https://example.com/images/cute_cat.jpg",
        "https://example.com/images/blue_ocean.png",
        "https://example.com/images/rocky_mountain.jpg",
        "https://example.com/images/happy_dog.jpeg",
        "https://example.com/images/kitty_play.jpg",
    ]

    success_count = 0
    fail_count = 0

    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()

    for i, url in enumerate(urls, 1):
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        inserted_id = cursor_a.lastrowid
        tags = mock_ai_tagging_api(url)

        # Giả lập lỗi ngẫu nhiên 30%
        if random.random() < 0.30:
            print(f"  [Ảnh {i}] id={inserted_id} → ❌ Site B timeout (giả lập) — BỎ QUA")
            fail_count += 1
        else:
            try:
                conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
                cursor_b = conn_b.cursor()
                cursor_b.execute(
                    "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
                    (inserted_id, url, tags)
                )
                conn_b.commit()
                conn_b.close()
                print(f"  [Ảnh {i}] id={inserted_id} → ✅ Đồng bộ Site B thành công.")
                success_count += 1
            except mysql.connector.Error as err:
                print(f"  [Ảnh {i}] id={inserted_id} → ❌ Lỗi: {err}")
                fail_count += 1

    conn_a.close()

    # Kiểm tra số liệu thực tế
    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    count_a = conn_a.cursor()
    count_a.execute("SELECT COUNT(*) FROM Image_Metadata")
    total_a = count_a.fetchone()[0]
    conn_a.close()

    conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
    count_b = conn_b.cursor()
    count_b.execute("SELECT COUNT(*) FROM Image_Metadata")
    total_b = count_b.fetchone()[0]
    conn_b.close()

    print(f"\n  KẾT QUẢ CUỐI: Site A = {total_a} records | Site B = {total_b} records")
    if total_a != total_b:
        print(f"  ⚠️  Mất đồng nhất! Chênh lệch {total_a - total_b} record.")
        print("  💡 Giải pháp: Reconciliation job định kỳ so sánh Site A vs Site B.")
    else:
        print("  ✅ Dữ liệu đồng nhất (may mắn không có lỗi lần này).")

# --------------------------------------------------
# LỖI 4: Cold Start gây timeout SLA
# --------------------------------------------------
def demo_loi_4_cold_start_timeout():
    separator("LỖI 4: Cold Start vượt ngưỡng SLA")
    print("► Mô tả: Hệ thống cam kết SLA xử lý mỗi ảnh trong vòng 0.5 giây.")
    print("         Cold Start (~1.5s) khiến lần đầu vi phạm SLA nghiêm trọng.\n")

    SLA_THRESHOLD = 0.5  # giây

    init_databases()
    reset_serverless_container()

    urls = [
        "https://example.com/images/cute_cat.jpg",   # lần 1: Cold
        "https://example.com/images/happy_dog.jpeg", # lần 2: Warm
        "https://example.com/images/blue_ocean.png", # lần 3: Warm
    ]

    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()

    for i, url in enumerate(urls, 1):
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        inserted_id = cursor_a.lastrowid

        elapsed = serverless_trigger_handler(inserted_id, url)
        status = "COLD" if i == 1 else "WARM"
        sla_ok = "✅ OK" if elapsed <= SLA_THRESHOLD else f"❌ VI PHẠM SLA (>{SLA_THRESHOLD}s)"
        print(f"  [Ảnh {i}] {status} | Thời gian: {elapsed:.3f}s | SLA: {sla_ok}")

    conn_a.close()
    print(f"\n  ⚠️  Nhận xét: Lần đầu (Cold Start) luôn vi phạm SLA {SLA_THRESHOLD}s.")
    print("  💡 Giải pháp: Provisioned Concurrency (giữ container ấm sẵn) hoặc nới SLA cho lần đầu.")

# --------------------------------------------------
# LỖI 5: Dữ liệu không nhất quán — Site A có nhưng Site B thiếu tags
# --------------------------------------------------
def demo_loi_5_inconsistent_data():
    separator("LỖI 5: Dữ liệu không nhất quán giữa Site A và Site B")
    print("► Mô tả: Trigger hoàn thành nhưng AI tagging trả về rỗng/lỗi.")
    print("         Site B nhận được record nhưng tags bị NULL hoặc sai.\n")

    init_databases()
    reset_serverless_container()

    def broken_ai_tagging(url):
        """Giả lập AI tagging bị lỗi: 50% trả về NULL"""
        time.sleep(0.05)
        if random.random() < 0.5:
            raise ValueError("AI service unavailable (timeout)")
        return mock_ai_tagging_api(url)

    urls = [
        "https://example.com/images/cute_cat.jpg",
        "https://example.com/images/rocky_mountain.jpg",
        "https://example.com/images/happy_dog.jpeg",
    ]

    conn_a = mysql.connector.connect(**MYSQL_CONFIG, database='site_a_db')
    cursor_a = conn_a.cursor()

    for i, url in enumerate(urls, 1):
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        inserted_id = cursor_a.lastrowid
        print(f"  [Site A] INSERT id={inserted_id} ✅")

        try:
            tags = broken_ai_tagging(url)
            status = f"tags='{tags}'"
        except ValueError as e:
            tags = None  # Vẫn INSERT vào Site B nhưng tags là NULL
            status = f"tags=NULL (AI lỗi: {e})"

        try:
            conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
            cursor_b = conn_b.cursor()
            cursor_b.execute(
                "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
                (inserted_id, url, tags)
            )
            conn_b.commit()
            conn_b.close()
            print(f"  [Site B] INSERT id={inserted_id} — {status}")
        except mysql.connector.Error as err:
            print(f"  [Site B] ❌ Lỗi: {err}")

    conn_a.close()

    # Kiểm tra bản ghi NULL tags
    conn_b = mysql.connector.connect(**MYSQL_CONFIG, database='site_b_db')
    cursor_b = conn_b.cursor()
    cursor_b.execute("SELECT id, url, tags FROM Image_Metadata")
    rows = cursor_b.fetchall()
    conn_b.close()

    null_count = sum(1 for r in rows if r[2] is None)
    print(f"\n Site B: {len(rows)} records | {null_count} record có tags=NULL")
    if null_count > 0:
        print("  ⚠️  Dữ liệu không nhất quán: record tồn tại nhưng tags bị mất!")
        print("  💡 Giải pháp: Lưu trạng thái 'pending' và chạy re-tagging job sau.")

# ================================
# MENU CHÍNH
# ================================
def main():
    while True:
        print("\n" + "="*60)
        print("  SERVERLESS DB TRIGGER — AUTOMATIC IMAGE TAGGING")
        print("  Dương Quốc Khánh | N23DCCN097")
        print("="*60)
        print("  [1] Benchmark: Thời gian xử lý vs Volume dữ liệu")
        print("  [2] Demo các lỗi hệ thống phân tán")
        print("  [0] Thoát")
        print("-"*60)
        choice = input("  Chọn: ").strip()

        if choice == '1':
            run_benchmark()

        elif choice == '2':
            print("\n  Chọn lỗi muốn demo:")
            print("  [1] Site B ngừng hoạt động (bảng bị DROP)")
            print("  [2] Duplicate Trigger — INSERT trùng ID")
            print("  [3] Partial Failure — đồng bộ một phần")
            print("  [4] Cold Start vượt ngưỡng SLA")
            print("  [5] Dữ liệu không nhất quán (tags=NULL)")
            print("  [6] Chạy tất cả 5 lỗi")
            sub = input("  Chọn: ").strip()

            if sub == '1':
                demo_loi_1_site_b_chet()
            elif sub == '2':
                demo_loi_2_duplicate_trigger()
            elif sub == '3':
                demo_loi_3_partial_failure()
            elif sub == '4':
                demo_loi_4_cold_start_timeout()
            elif sub == '5':
                demo_loi_5_inconsistent_data()
            elif sub == '6':
                demo_loi_1_site_b_chet()
                demo_loi_2_duplicate_trigger()
                demo_loi_3_partial_failure()
                demo_loi_4_cold_start_timeout()
                demo_loi_5_inconsistent_data()
            else:
                print("  ⚠️  Lựa chọn không hợp lệ.")

        elif choice == '0':
            print("\n  👋 Thoát chương trình.")
            break
        else:
            print("  ⚠️  Lựa chọn không hợp lệ, vui lòng thử lại.")

if __name__ == '__main__':
    main()
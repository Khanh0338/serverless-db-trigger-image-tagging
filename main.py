import mysql.connector
import time
import random
import os

# ================================
# CẤU HÌNH KẾT NỐI ĐA NODE (DOCKER NETWORKING)
# ================================
DB_USER = "root"
DB_PASS = "123456"
DB_A_HOST = "site_a"  # Tên service của Container Site A trong Docker Compose
DB_B_HOST = "site_b"  # Tên service của Container Site B trong Docker Compose

# ================================
# 1. KHỞI TẠO CƠ SỞ DỮ LIỆU
# ================================
def init_databases():
    # --- Khởi tạo Site A ---
    conn_a = mysql.connector.connect(host=DB_A_HOST, user=DB_USER, password=DB_PASS)
    cursor_a = conn_a.cursor()
    cursor_a.execute("CREATE DATABASE IF NOT EXISTS site_a_db")
    cursor_a.execute("USE site_a_db")
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

    # --- Khởi tạo Site B + Bảng Dead Letter Queue (DLQ) ---
    conn_b = mysql.connector.connect(host=DB_B_HOST, user=DB_USER, password=DB_PASS)
    cursor_b = conn_b.cursor()
    cursor_b.execute("CREATE DATABASE IF NOT EXISTS site_b_db")
    cursor_b.execute("USE site_b_db")
    cursor_b.execute("""
        CREATE TABLE IF NOT EXISTS Image_Metadata (
            id INT PRIMARY KEY,
            url VARCHAR(255),
            tags VARCHAR(255)
        )
    """)
    cursor_b.execute("""
        CREATE TABLE IF NOT EXISTS Dead_Letter_Queue (
            id INT AUTO_INCREMENT PRIMARY KEY,
            image_id INT,
            url VARCHAR(255),
            reason VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor_b.execute("TRUNCATE TABLE Image_Metadata")
    cursor_b.execute("TRUNCATE TABLE Dead_Letter_Queue")
    conn_b.commit()
    conn_b.close()
    print("[DB] Khởi tạo cấu trúc dữ liệu thành công trên Site A và Site B.")

# ================================
# 2. GIẢ LẬP SERVERLESS FUNCTION (AWS LAMBDA)
# ================================
IS_CONTAINER_WARM = False

def reset_serverless_container():
    global IS_CONTAINER_WARM
    IS_CONTAINER_WARM = False

def mock_ai_tagging_api(url):
    time.sleep(0.05)
    url_lower = url.lower()
    tags = []
    if 'cat' in url_lower or 'kitty' in url_lower: tags.extend(['animal', 'cat', 'pet'])
    if 'dog' in url_lower or 'puppy' in url_lower: tags.extend(['animal', 'dog', 'pet'])
    if 'ocean' in url_lower or 'beach' in url_lower: tags.extend(['nature', 'sea', 'water'])
    if 'mountain' in url_lower: tags.extend(['nature', 'land', 'mountain'])
    return ", ".join(tags) if tags else "general, uncategorized"

def log_to_dlq(image_id, url, reason):
    """Ghi lỗi vào Dead Letter Queue khi đồng bộ thất bại"""
    try:
        conn = mysql.connector.connect(host=DB_B_HOST, user=DB_USER, password=DB_PASS, database='site_b_db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Dead_Letter_Queue (image_id, url, reason) VALUES (%s, %s, %s)",
            (image_id, url, str(reason))
        )
        conn.commit()
        conn.close()
        print(f"  [DLQ] Đã lưu log lỗi của ID {image_id} vào Dead Letter Queue.")
    except Exception as e:
        print(f"  ⚠️ Không thể ghi log vào DLQ: {e}")

def serverless_trigger_handler(image_id, url, force_fail=False):
    global IS_CONTAINER_WARM
    start_time = time.time()

    is_cold = False
    if not IS_CONTAINER_WARM:
        time.sleep(1.5)  # Giả lập Cold Start
        IS_CONTAINER_WARM = True
        is_cold = True

    computed_tags = mock_ai_tagging_api(url)

    if force_fail:
        log_to_dlq(image_id, url, "Simulated Network Failure")
        return time.time() - start_time, is_cold, False

    try:
        conn_b = mysql.connector.connect(host=DB_B_HOST, user=DB_USER, password=DB_PASS, database='site_b_db')
        cursor_b = conn_b.cursor()
        cursor_b.execute(
            "INSERT INTO Image_Metadata (id, url, tags) VALUES (%s, %s, %s)",
            (image_id, url, computed_tags)
        )
        conn_b.commit()
        conn_b.close()
        success = True
    except mysql.connector.Error as err:
        log_to_dlq(image_id, url, err)
        success = False

    return time.time() - start_time, is_cold, success

# ================================
# 3. CHÈN DỮ LIỆU VÀO SITE A
# ================================
def insert_to_site_a_and_trigger(url_list):
    conn_a = mysql.connector.connect(host=DB_A_HOST, user=DB_USER, password=DB_PASS, database='site_a_db')
    cursor_a = conn_a.cursor()
    results = []

    for url in url_list:
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        inserted_id = cursor_a.lastrowid
        
        elapsed, is_cold, success = serverless_trigger_handler(inserted_id, url)
        results.append({'elapsed': elapsed, 'is_cold': is_cold, 'success': success})

    conn_a.close()
    return results

# ================================
# 4. BENCHMARK (XUẤT REPORT RA VOLUME)
# ================================
def run_benchmark():
    separator("ĐO LƯỜNG: AVERAGE EXECUTION TIME VS DATA VOLUME")
    test_volumes = [1, 5, 20, 50]

    def generate_mock_urls(count):
        samples = [
            "https://example.com/images/cute_cat.jpg",
            "https://example.com/images/blue_ocean.png",
            "https://example.com/images/rocky_mountain.jpg",
            "https://example.com/images/happy_dog.jpeg"
        ]
        return [samples[i % len(samples)] for i in range(count)]

    report_lines = []
    header = f"{'Volume (Số ảnh)':<15}{'Tổng thời gian (s)':<22}{'Thời gian TB / Ảnh (s)':<22}"
    print(header)
    print("-" * 60)
    report_lines.append(header)
    report_lines.append("-" * 60)

    for volume in test_volumes:
        init_databases()
        reset_serverless_container()
        urls = generate_mock_urls(volume)
        
        results = insert_to_site_a_and_trigger(urls)
        total_time = sum(r['elapsed'] for r in results)
        avg_time = total_time / volume
        
        row = f"{volume:<15}{total_time:<22.4f}{avg_time:<22.4f}"
        print(row)
        report_lines.append(row)

    # Xuất file báo cáo ra thư mục share volume `/app/output`
    try:
        output_path = "/app/output/benchmark_report.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\n📝 Đã xuất báo cáo chi tiết ra: {output_path}")
    except Exception as e:
        print(f"⚠️ Không thể lưu file báo cáo: {e}")

# ================================
# 5. DEMO CÁC LỖI HỆ THỐNG PHÂN TÁN
# ================================
def separator(title):
    print(f"\n" + "="*60 + f"\n  {title}\n" + "="*60)

def demo_loi_1_site_b_chet():
    separator("LỖI 1: Site B ngừng hoạt động (Bảng đích bị sập)")
    init_databases()
    reset_serverless_container()

    conn_b = mysql.connector.connect(host=DB_B_HOST, user=DB_USER, password=DB_PASS, database='site_b_db')
    cursor_b = conn_b.cursor()
    cursor_b.execute("DROP TABLE IF EXISTS Image_Metadata")
    conn_b.commit()
    conn_b.close()

    print("  [Simulate] Đã xóa bảng Image_Metadata tại Site B.")
    insert_to_site_a_and_trigger(["https://example.com/images/cute_cat.jpg"])

def demo_loi_2_duplicate_trigger():
    separator("LỖI 2: Duplicate Trigger (INSERT trùng lặp ID)")
    init_databases()
    reset_serverless_container()

    url = "https://example.com/images/blue_ocean.png"
    print("  [Trigger] Gọi xử lý lần đầu:")
    serverless_trigger_handler(100, url)
    
    print("\n  [Trigger] Gói tin bị lặp, gửi lại ID cũ (100):")
    serverless_trigger_handler(100, url)

def demo_loi_3_partial_failure():
    separator("LỖI 3: Partial Failure (Lỗi mạng cục bộ)")
    init_databases()
    reset_serverless_container()

    urls = ["https://example.com/images/cute_cat.jpg", "https://example.com/images/happy_dog.jpeg"]
    conn_a = mysql.connector.connect(host=DB_A_HOST, user=DB_USER, password=DB_PASS, database='site_a_db')
    cursor_a = conn_a.cursor()

    for i, url in enumerate(urls, 1):
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        force_fail = (i == 2)
        if force_fail:
            print(f"  [Network] Giả lập mất kết nối khi xử lý ảnh thứ {i}")
        serverless_trigger_handler(cursor_a.lastrowid, url, force_fail=force_fail)
    conn_a.close()

def demo_loi_4_cold_start_timeout():
    separator("LỖI 4: Cold Start vượt ngưỡng SLA")
    SLA_THRESHOLD = 0.5
    init_databases()
    reset_serverless_container()

    urls = ["https://example.com/images/cute_cat.jpg", "https://example.com/images/happy_dog.jpeg"]
    conn_a = mysql.connector.connect(host=DB_A_HOST, user=DB_USER, password=DB_PASS, database='site_a_db')
    cursor_a = conn_a.cursor()

    for i, url in enumerate(urls, 1):
        cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
        conn_a.commit()
        elapsed, is_cold, _ = serverless_trigger_handler(cursor_a.lastrowid, url)
        
        status = "COLD START" if is_cold else "WARM RUN"
        sla_ok = "✅ Đạt SLA" if elapsed <= SLA_THRESHOLD else f"❌ Vi phạm SLA (>{SLA_THRESHOLD}s)"
        print(f"  [Ảnh {i}] Trạng thái: {status:<12} | Thời gian: {elapsed:.3f}s | Kết luận: {sla_ok}")
    conn_a.close()

def demo_loi_5_inconsistent_data():
    separator("LỖI 5: Dữ liệu không nhất quán (Mất thuộc tính Tag)")
    init_databases()
    reset_serverless_container()

    url = "https://example.com/images/unknown_item.zip"
    conn_a = mysql.connector.connect(host=DB_A_HOST, user=DB_USER, password=DB_PASS, database='site_a_db')
    cursor_a = conn_a.cursor()
    cursor_a.execute("INSERT INTO Image_Metadata (url) VALUES (%s)", (url,))
    conn_a.commit()
    
    serverless_trigger_handler(cursor_a.lastrowid, url)
    conn_a.close()

    conn_b = mysql.connector.connect(host=DB_B_HOST, user=DB_USER, password=DB_PASS, database='site_b_db')
    cursor_b = conn_b.cursor()
    cursor_b.execute("SELECT * FROM Image_Metadata")
    row = cursor_b.fetchone()
    print(f"  [Kiểm toán Site B] ID: {row[0]} | URL: {row[1]} | Thẻ phân tích: {row[2]}")
    conn_b.close()

# ================================
# MAIN MENU
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
            print("\n  Chọn lỗi muốn demo:\n  [1] Site B ngừng hoạt động\n  [2] Duplicate Trigger\n  [3] Partial Failure\n  [4] Cold Start vượt SLA\n  [5] Dữ liệu không nhất quán\n  [6] Chạy tất cả lỗi")
            sub = input("  Chọn: ").strip()
            if sub == '1': demo_loi_1_site_b_chet()
            elif sub == '2': demo_loi_2_duplicate_trigger()
            elif sub == '3': demo_loi_3_partial_failure()
            elif sub == '4': demo_loi_4_cold_start_timeout()
            elif sub == '5': demo_loi_5_inconsistent_data()
            elif sub == '6':
                demo_loi_1_site_b_chet(); demo_loi_2_duplicate_trigger(); demo_loi_3_partial_failure(); demo_loi_4_cold_start_timeout(); demo_loi_5_inconsistent_data()
        elif choice == '0':
            break

if __name__ == '__main__':
    main()
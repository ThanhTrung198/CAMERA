import mysql.connector
import json

# Cấu hình DB
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "", 
    "database": "ai_nckh"
}

def check_db():
    print("\n--- BẮT ĐẦU KIỂM TRA DỮ LIỆU DATABASE ---")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 1. KIỂM TRA BẢNG NHÂN VIÊN
        print("\n1️⃣  Kiểm tra bảng 'nhan_vien':")
        cursor.execute("SELECT ma_nv, ho_ten FROM nhan_vien")
        users = cursor.fetchall()
        if not users:
            print("   ❌ Bảng 'nhan_vien' ĐANG TRỐNG! (Chưa có ai cả)")
        else:
            print(f"   ✅ Có {len(users)} nhân viên.")
            for u in users:
                print(f"      - ID: {u['ma_nv']} | Tên: {u['ho_ten']}")

        # 2. KIỂM TRA BẢNG FACE_EMBEDDINGS
        print("\n2️⃣  Kiểm tra bảng 'face_embeddings':")
        cursor.execute("SELECT id, ma_nv, vector_data FROM face_embeddings")
        faces = cursor.fetchall()
        if not faces:
            print("   ❌ Bảng 'face_embeddings' ĐANG TRỐNG! (Chưa có khuôn mặt nào được lưu)")
            print("   👉 Nguyên nhân: Có thể lúc thêm nhân viên bị lỗi, hoặc anh chưa bấm thêm ảnh.")
        else:
            print(f"   ✅ Có {len(faces)} dữ liệu khuôn mặt.")
            for f in faces:
                data_len = len(str(f['vector_data']))
                print(f"      - ID Bảng: {f['id']} | Gắn với ma_nv: {f['ma_nv']} | Độ dài Vector: {data_len} ký tự")
                
                # Kiểm tra xem có khớp với nhân viên nào không
                found = False
                for u in users:
                    if u['ma_nv'] == f['ma_nv']:
                        found = True
                        print(f"        -> ✅ Khớp với nhân viên: {u['ho_ten']}")
                        break
                if not found:
                    print(f"        -> 🔴 CẢNH BÁO: ma_nv {f['ma_nv']} không tồn tại trong bảng nhan_vien! (Dữ liệu rác)")

        # 3. KIỂM TRA KẾT QUẢ CUỐI CÙNG (JOIN)
        print("\n3️⃣  Kiểm tra lệnh JOIN (Cái mà app.py dùng):")
        sql = """
            SELECT nv.ho_ten, fe.vector_data 
            FROM face_embeddings fe
            JOIN nhan_vien nv ON fe.ma_nv = nv.ma_nv
        """
        cursor.execute(sql)
        final_rows = cursor.fetchall()
        print(f"   👉 Tổng số mặt App đọc được: {len(final_rows)}")

        if len(final_rows) == 0:
            print("\n🚨 KẾT LUẬN: App không chạy được vì không có dữ liệu ghép đôi hợp lệ.")
        else:
            print("\n✅ KẾT LUẬN: Dữ liệu ổn. Nếu App vẫn không nhận thì do định dạng Vector sai (JSON vs Bytes).")

        conn.close()

    except Exception as e:
        print(f"❌ Lỗi kết nối Database: {e}")

if __name__ == "__main__":
    check_db()
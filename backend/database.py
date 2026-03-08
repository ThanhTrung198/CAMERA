import mysql.connector

def get_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",     # Nếu có mật khẩu thì điền vào đây
            database="ai_nckh",
            port=3306,
            charset='utf8mb4'
        )
        return connection
    except mysql.connector.Error as err:
        print("Lỗi kết nối:", err)
        return None

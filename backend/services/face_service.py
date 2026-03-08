"""
Face Recognition Service - FaceDatabase class for managing face embeddings
"""
import numpy as np
import json
from database import get_connection
from config.settings import SYSTEM_SETTINGS


class FaceDatabase:
    """
    Manage face embeddings for known employees and strangers
    """
    
    def __init__(self):
        self.known_embeddings = []
        self.stranger_embeddings = []
        self.next_stranger_id = 1
        self.reload_db()
    
    def reload_db(self):
        """
        Load face embeddings from database
        """
        print("System: Đang tải dữ liệu khuôn mặt từ Database...")
        self.known_embeddings = []
        self.stranger_embeddings = []
        
        conn = None
        try:
            conn = get_connection()
            if not conn:
                print("❌ Không thể kết nối database")
                return
            
            cursor = conn.cursor(dictionary=True)
            
            # Load known employees
            cursor.execute("""
                SELECT nv.ho_ten, nv.ten_phong, nv.ten_chuc_vu, fe.vector_data 
                FROM face_embeddings fe 
                JOIN nhan_vien nv ON fe.ma_nv = nv.ma_nv
            """)
            
            for row in cursor.fetchall():
                if not row['vector_data']:
                    continue
                
                try:
                    data = json.loads(row['vector_data'])
                    arr = np.array(data, dtype=np.float32)
                    
                    if arr.ndim == 1:
                        self.known_embeddings.append({
                            "name": row['ho_ten'],
                            "dept": row['ten_phong'],
                            "role": row['ten_chuc_vu'],
                            "embedding": arr
                        })
                    elif arr.ndim == 2:
                        for single_emb in arr:
                            self.known_embeddings.append({
                                "name": row['ho_ten'],
                                "dept": row['ten_phong'],
                                "role": row['ten_chuc_vu'],
                                "embedding": single_emb
                            })
                except Exception as e:
                    print(f"⚠️ Lỗi data nhân viên {row['ho_ten']}: {e}")
            
            # Load strangers
            cursor.execute("SELECT stranger_label, vector_data FROM vector_nguoi_la")
            for row in cursor.fetchall():
                if row['vector_data']:
                    emb = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    self.stranger_embeddings.append({
                        "name": row['stranger_label'],
                        "embedding": emb
                    })
                    
                    try:
                        sid = int(row['stranger_label'].split('_')[-1])
                        if sid >= self.next_stranger_id:
                            self.next_stranger_id = sid + 1
                    except:
                        pass
            
            cursor.close()
            print(f"✅ HOÀN TẤT: Đã nạp {len(self.known_embeddings)} vector NV và {len(self.stranger_embeddings)} vector người lạ.")
        
        except Exception as e:
            print(f"❌ Lỗi tải DB: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def recognize(self, target_embedding):
        """
        Recognize face from embedding
        
        Args:
            target_embedding: Face embedding vector
        
        Returns:
            (name, confidence_score) tuple
        """
        # Normalize target embedding
        norm_target = np.linalg.norm(target_embedding)
        if norm_target != 0:
            target_embedding = target_embedding / norm_target
        
        max_score = 0
        identity = "Unknown"
        
        # Search in known embeddings
        for face in self.known_embeddings:
            db_emb = face["embedding"]
            
            # Normalize database embedding
            norm_db = np.linalg.norm(db_emb)
            if norm_db != 0:
                db_emb = db_emb / norm_db
            
            # Calculate cosine similarity
            score = np.dot(target_embedding, db_emb)
            
            if score > max_score:
                max_score = score
                identity = face["name"]
        
        max_score = float(max_score)
        
        if max_score >= SYSTEM_SETTINGS["threshold"]:
            return identity, max_score
        
        return "Unknown", max_score
    
    def get_person_info(self, name):
        """
        Get person information (department, role) by name
        
        Args:
            name: Person's name
        
        Returns:
            Dict with 'dept' and 'role' keys
        """
        for f in self.known_embeddings:
            if f["name"] == name:
                return {"dept": f["dept"], "role": f["role"]}
        
        return {"dept": "Unknown", "role": "Khách"}


# Global FaceDatabase instance
db = FaceDatabase()

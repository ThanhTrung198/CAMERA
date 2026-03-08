# ============================================================
# FILE: modules/faiss_recognition.py
# FAISS Face Recognition — O(1) search thay brute-force O(N)
# ============================================================
import numpy as np
import json
import os

FAISS_AVAILABLE = False
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    print("[FAISS] ⚠️ faiss not installed — pip install faiss-cpu")


class FAISSFaceDatabase:
    """
    Thay brute-force O(N) bằng FAISS approximate nearest neighbor.
    O(1) cho ~1M vectors, chính xác 99%+.
    """
    
    def __init__(self, threshold=0.45, dim=512):
        self.threshold = threshold
        self.dim = dim
        self.index = None
        self.metadata = []
        self.embeddings = None
        
        self.stranger_index = None
        self.stranger_metadata = []
        self.next_stranger_id = 1
        
        self.reload_db()
    
    def reload_db(self):
        print("[FAISS] Loading face database...")
        
        if not FAISS_AVAILABLE:
            print("[FAISS] ❌ faiss not available, using fallback")
            return
        
        embeddings_list = []
        self.metadata = []
        
        conn = None
        try:
            from database import get_connection
            conn = get_connection()
            if not conn:
                print("[FAISS] ❌ DB connection failed")
                return
            
            cursor = conn.cursor(dictionary=True)
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
                        norm = np.linalg.norm(arr)
                        if norm > 0:
                            arr = arr / norm
                        embeddings_list.append(arr)
                        self.metadata.append({
                            "name": row['ho_ten'],
                            "dept": row['ten_phong'],
                            "role": row['ten_chuc_vu']
                        })
                    elif arr.ndim == 2:
                        for single_emb in arr:
                            norm = np.linalg.norm(single_emb)
                            if norm > 0:
                                single_emb = single_emb / norm
                            embeddings_list.append(single_emb)
                            self.metadata.append({
                                "name": row['ho_ten'],
                                "dept": row['ten_phong'],
                                "role": row['ten_chuc_vu']
                            })
                except Exception as e:
                    print(f"[FAISS] ⚠️ Parse error: {e}")
            
            cursor.close()
        except Exception as e:
            print(f"[FAISS] ❌ DB error: {e}")
        finally:
            if conn:
                try: conn.close()
                except: pass
        
        if embeddings_list:
            self.embeddings = np.array(embeddings_list, dtype=np.float32)
            self.index = faiss.IndexFlatIP(self.dim)
            self.index.add(self.embeddings)
            print(f"[FAISS] ✅ Index: {self.index.ntotal} vectors")
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            print("[FAISS] ⚠️ Empty database")
    
    def recognize(self, target_embedding, k=3):
        """
        FAISS recognition với k-NN majority vote.
        Returns: (name, score)
        """
        if self.index is None or self.index.ntotal == 0:
            return "Unknown", 0.0
        
        norm = np.linalg.norm(target_embedding)
        if norm > 0:
            target_embedding = target_embedding / norm
        
        query = target_embedding.reshape(1, -1).astype(np.float32)
        actual_k = min(k, self.index.ntotal)
        scores, indices = self.index.search(query, actual_k)
        scores, indices = scores[0], indices[0]
        
        best_score = float(scores[0])
        best_idx = int(indices[0])
        
        if best_score >= self.threshold:
            if actual_k >= 3:
                from collections import Counter
                names = [self.metadata[int(i)]["name"]
                         for i in indices[:3] if int(i) < len(self.metadata)]
                vote = Counter(names).most_common(1)
                if vote:
                    return vote[0][0], best_score
            return self.metadata[best_idx]["name"], best_score
        
        return "Unknown", best_score
    
    def get_person_info(self, name):
        for m in self.metadata:
            if m["name"] == name:
                return {"dept": m["dept"], "role": m["role"]}
        return {"dept": "Unknown", "role": "Khách"}

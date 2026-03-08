# face_database.py
import json
import numpy as np
from database import get_db

def load_all_embeddings():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT nv.ma_nv, nv.ho_ten, fe.embedding
        FROM face_embeddings fe
        JOIN nhan_vien nv ON fe.employee_id = nv.ma_nv
    """)

    rows = cursor.fetchall()
    cursor.close()
    db.close()

    embeddings = []
    for row in rows:
        embeddings.append({
            "employee_id": row["ma_nv"],
            "name": row["ho_ten"],
            "embedding": np.array(json.loads(row["embedding"]))
        })
def reload_db(self):
    self.known_embeddings = {}
    for f in os.listdir("face_db"):
        if f.endswith(".npy"):
            ma_nv = int(f.replace("nv_", "").replace(".npy", ""))
            emb = np.load(os.path.join("face_db", f))
            emb = emb / np.linalg.norm(emb)
            self.known_embeddings[ma_nv] = emb


def recognize(self, target_embedding):
    max_score = 0
    best_ma_nv = None

    target_embedding = target_embedding / np.linalg.norm(target_embedding)

    for ma_nv, db_emb in self.known_embeddings.items():
        score = np.dot(target_embedding, db_emb)
        if score > max_score:
            max_score = score
            best_ma_nv = ma_nv

    if max_score >= 0.65:
        return best_ma_nv, max_score

    return None, max_score
def save_face_embedding(ma_nv, image_path):
    img = cv2.imread(image_path)
    faces = app.get(img)

    if len(faces) != 1:
        raise Exception("Ảnh phải có đúng 1 khuôn mặt")

    emb = faces[0].embedding
    np.save(f"face_db/nv_{ma_nv}.npy", emb)

    return embeddings
    
# face_recognition.py
import numpy as np
from numpy.linalg import norm

faces = self.app.get(frame)
for face in faces:
    ma_nv, score = self.recognize(face.embedding)
def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

def recognize_face(face_embedding, db_embeddings, threshold=0.45):
    best_match = None
    best_score = -1

    for item in db_embeddings:
        score = cosine_similarity(face_embedding, item["embedding"])
        if score > best_score:
            best_score = score
            best_match = item

    if best_score >= threshold:
        return {
            "employee_id": best_match["employee_id"],
            "name": best_match["name"],
            "confidence": float(best_score)
        }

    return None

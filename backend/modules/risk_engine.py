# ============================================================
# FILE: modules/risk_engine.py
# Adaptive Risk Scoring Engine
# ============================================================
from datetime import datetime


class AdaptiveRiskEngine:
    """
    Chấm điểm rủi ro động cho mỗi sự kiện.
    
    Risk Levels:
      0: SAFE       — nhân viên đã biết, mặt thật
      1: LOW        — người lạ, mặt thật
      2: MEDIUM     — kết quả spoof phân vân
      3: HIGH       — giả mạo xác nhận
      4: CRITICAL   — giả mạo liên tục + zone intrusion
    """
    
    LEVEL_NAMES = {0: "SAFE", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
    ACTIONS = {
        0: "ALLOW",
        1: "LOG",
        2: "MONITOR + STEP-UP",
        3: "ALERT + RECORD",
        4: "BLOCK + ALERT + RECORD",
    }
    
    def __init__(self):
        self.person_risk_history = {}
    
    def calculate_risk(self, name, is_real, spoof_conf,
                        zone_intrusion=False, cam_id=0,
                        consecutive_fake=0, time_of_day=None):
        base_risk = 0
        factors = []
        
        # Factor 1: Identity
        if name == "GIA MAO" or not is_real:
            base_risk += 40
            factors.append(("spoof_detected", 40))
        elif name == "Unknown":
            base_risk += 15
            factors.append(("stranger", 15))
        else:
            base_risk -= 10
            factors.append(("known_employee", -10))
        
        # Factor 2: Spoof confidence
        if spoof_conf >= 0.80:
            base_risk += 30
            factors.append(("high_spoof_conf", 30))
        elif spoof_conf >= 0.60:
            base_risk += 15
            factors.append(("medium_spoof_conf", 15))
        
        # Factor 3: Zone intrusion
        if zone_intrusion:
            base_risk += 25
            factors.append(("zone_intrusion", 25))
        
        # Factor 4: Consecutive fake
        if consecutive_fake >= 10:
            base_risk += 20
            factors.append(("persistent_attack", 20))
        elif consecutive_fake >= 5:
            base_risk += 10
            factors.append(("repeated_fake", 10))
        
        # Factor 5: Off-hours
        if time_of_day is None:
            time_of_day = datetime.now()
        hour = time_of_day.hour
        if hour < 6 or hour > 22:
            base_risk += 10
            factors.append(("off_hours", 10))
        
        risk_score = max(0, min(100, base_risk))
        
        if risk_score >= 70:   level = 4
        elif risk_score >= 50: level = 3
        elif risk_score >= 30: level = 2
        elif risk_score >= 10: level = 1
        else:                  level = 0
        
        return {
            "risk_score": risk_score,
            "risk_level": level,
            "risk_name": self.LEVEL_NAMES[level],
            "action": self.ACTIONS[level],
            "factors": factors,
        }

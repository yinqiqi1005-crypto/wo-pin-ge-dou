IRONING_METHODS = {
    "light_single": {
        "code": "light_single",
        "name": "轻烫保孔",
        "effect_position": "top-left",
        "best_for": "装框展示、希望保留豆孔的作品",
        "reason": "轻烫能固定作品，同时尽量保留豆孔和颗粒感。",
        "materials": "熨斗、烫纸、平整耐热桌面",
        "steps": "中低温隔烫纸轻压，画小圈移动；冷却前不要掀起作品。",
        "safety": "熨斗持续移动，不要直接接触拼豆；完全冷却后再取下。",
    },
    "standard_single": {
        "code": "standard_single",
        "name": "标准单面烫",
        "effect_position": "top-right",
        "best_for": "大型拼接、一般摆件和不确定用途",
        "reason": "牢固度和豆孔保留较平衡，适合第一次制作时优先选择。",
        "materials": "熨斗、烫纸、厚书或压板",
        "steps": "中温隔纸均匀移动，表面轻微融合后压平冷却。",
        "safety": "不要停在同一处；压平时隔纸，避免烫伤和粘连。",
    },
    "double_sided": {
        "code": "double_sided",
        "name": "双面加固烫",
        "effect_position": "bottom-left",
        "best_for": "挂件、日常使用和需要更牢固的作品",
        "reason": "双面加固更牢固，适合经常拿取或受力的成品。",
        "materials": "熨斗、两张烫纸、压板",
        "steps": "一面标准烫并冷却，翻面后短时间补烫，再平压冷却。",
        "safety": "先完全冷却再翻面；第二面时间更短，避免过融变形。",
    },
    "flat_press": {
        "code": "flat_press",
        "name": "平整压制烫",
        "effect_position": "bottom-right",
        "best_for": "杯垫等平面用品",
        "reason": "更平整、不易翘边，适合需要稳定放置的平面作品。",
        "materials": "熨斗、烫纸、平整压板或厚书",
        "steps": "完成标准单面烫后，在烫纸保护下用压板平压至完全冷却。",
        "safety": "不要追求完全融平；豆孔过度闭合会让作品失去结构。",
    },
}


def recommend_ironing_method(finished_use: str, *, width: int, height: int) -> dict:
    if finished_use == "display":
        code = "light_single"
    elif finished_use == "daily":
        code = "double_sided"
    elif finished_use == "flat":
        code = "flat_press"
    else:
        code = "standard_single"
    recommendation = {**IRONING_METHODS[code]}
    recommendation["alternatives"] = [
        method for method_code, method in IRONING_METHODS.items() if method_code != code
    ]
    recommendation["pattern_size"] = f"{width}×{height}"
    return recommendation

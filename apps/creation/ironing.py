"""User-selectable ironing guidance based on documented bead-fusing methods."""

IRONING_STYLES = {
    "standard_two_sided": {
        "code": "standard_two_sided",
        "name": "标准双面半烫（保留豆孔）",
        "effect": "正反两面轻度融合，豆孔仍清晰，保留颗粒感。",
        "best_for": "人物、宠物、风景、动漫等绝大多数平面图案。",
        "reason": "这是最稳妥的入门做法：作品有足够连接力，也便于保留颜色与细节。",
        "materials": "熨斗、烫纸、平整耐热桌面、压板或厚书。",
        "steps": "中温隔烫纸画小圈移动，看到豆孔轻微收口就停；冷却后翻面，再短时间补烫。",
        "safety": "不要在同一处停留或用力下压；完全冷却后再移动作品。",
        "source_url": "https://perler.com/blogs/projects/standard-fusing-method",
        "source_label": "查看官方标准熔合示例",
        "diagram": "open-holes",
    },
    "single_sided_shape": {
        "code": "single_sided_shape",
        "name": "单面烫与热塑形",
        "effect": "一面融合、另一面保留纹理；趁热可弯折成有弧度的部件。",
        "best_for": "立体小物、支架、需要拼接或希望保留反面纹理的图案。",
        "reason": "它服务于造型和装配，不是一般平面图纸的默认做法。",
        "materials": "熨斗、烫纸、耐热手套或工具、定型支撑物。",
        "steps": "只烫需要融合的一面；在仍温热时轻轻弯折或放入支撑物定型。",
        "safety": "高温会让孔闭合，插槽可能无法装配；塑形时避免直接触摸热作品。",
        "source_url": "https://perler.com/blogs/projects/cell-phone-stands",
        "source_label": "查看官方单面烫与立体支架案例",
        "diagram": "single-side",
    },
    "flat_melt": {
        "code": "flat_melt",
        "name": "平烫全熔（平滑表面）",
        "effect": "豆孔大幅闭合，表面更平滑、更接近一整片塑料。",
        "best_for": "追求平滑质感的装饰画、杯垫与现代图形；不适合依赖豆孔的细节风格。",
        "reason": "选择它是为了视觉效果，不是为了替代标准加固；它会改变像素颗粒感。",
        "materials": "熨斗、烫纸、平整耐热桌面、压板或厚书。",
        "steps": "在烫纸下均匀延长熔合时间，观察豆孔逐渐闭合；两面完成后平压冷却。",
        "safety": "过热会变形、发亮或粘纸；先拿小样测试温度和时间。",
        "source_url": "https://perler.com/pages/frequently-asked-questions",
        "source_label": "查看官方熔合与冷却说明",
        "diagram": "flat-melt",
    },
    "large_project_tape": {
        "code": "large_project_tape",
        "name": "多板胶带翻面法",
        "effect": "用胶带固定大图案后翻面熔合，减少多块拼板移动时散落或错位。",
        "best_for": "大型人物、风景、海报式图案，以及跨多块拼板的作品。",
        "reason": "这是大作品的操作方法；熔合程度仍可选保孔或平烫。",
        "materials": "美纹胶或专用胶带、熨斗、烫纸、平整大桌面、压板。",
        "steps": "完成排豆后贴带固定并打孔排气，翻面分区熔合；压平并彻底冷却后再揭带。",
        "safety": "逐区烫，不要直接烫胶带；大作品移动与翻面最好由成年人协助。",
        "source_url": "https://perler.com/blogs/projects/the-tape-method-for-fusing-large-projects",
        "source_label": "查看官方多板胶带法案例",
        "diagram": "tape-method",
    },
}


def get_ironing_style(code: str) -> dict:
    """Return a safe, documented baseline for old or unknown saved versions."""
    return IRONING_STYLES.get(code, IRONING_STYLES["standard_two_sided"])

def ui_language(request):
    return {"ui_language": getattr(request, "ui_language", "zh-Hans")}

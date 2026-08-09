from apps.accounts.models import UserProfile

from .language import translate_html


class LanguagePreferenceMiddleware:
    session_key = "wpgd-language"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.session.get(self.session_key, "zh-Hans")
        if getattr(request, "user", None) and request.user.is_authenticated:
            language = UserProfile.objects.filter(user=request.user).values_list(
                "preferred_language", flat=True
            ).first() or language
        request.ui_language = language
        response = self.get_response(request)
        if (
            language != "zh-Hans"
            and not response.streaming
            and response.get("Content-Type", "").startswith("text/html")
        ):
            content = response.content.decode(response.charset)
            response.content = translate_html(content, language).encode(response.charset)
        return response

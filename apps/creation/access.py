import uuid

from django.contrib.auth import get_user_model

from apps.accounts.models import UserProfile

GUEST_SESSION_KEY = "creation_guest_user_id"


def effective_creation_user(request):
    if request.user.is_authenticated:
        return request.user
    user_model = get_user_model()
    guest_id = request.session.get(GUEST_SESSION_KEY)
    if guest_id:
        guest = user_model.objects.filter(pk=guest_id, profile__is_guest=True).first()
        if guest:
            return guest
    guest = user_model.objects.create_user(username=f"guest-{uuid.uuid4().hex}")
    guest.set_unusable_password()
    guest.save(update_fields=("password",))
    UserProfile.objects.update_or_create(
        user=guest,
        defaults={"display_name": "免费游客", "is_guest": True},
    )
    request.session[GUEST_SESSION_KEY] = guest.pk
    return guest

"""A trivial static-bearer resolver for tests (stands in for a real
``UserProfile.user_for_token``)."""


class FakeUser:
    pk = 7
    username = "bob"
    is_active = True


def user_for_token(token):
    return FakeUser() if token == "good-token" else None


def user_for_token_db(token):
    """Resolve a real DB user by username == token (used to test ORM-backed perms
    through the live ASGI stack)."""
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username=token, is_active=True).first()

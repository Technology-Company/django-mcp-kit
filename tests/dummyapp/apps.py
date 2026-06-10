from django.apps import AppConfig


class DummyAppConfig(AppConfig):
    name = "tests.dummyapp"
    label = "dummyapp"
    default_auto_field = "django.db.models.BigAutoField"

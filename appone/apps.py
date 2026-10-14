from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_admin_superuser(sender, **kwargs):
    try:
        from django.conf import settings
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_username = getattr(settings, "COLLEGE_ADMIN_USERNAME", "admin123")
        User.objects.filter(username=admin_username).update(is_staff=True, is_superuser=True)
    except Exception:
        pass


class ApponeConfig(AppConfig):
    name = 'appone'

    def ready(self):
        post_migrate.connect(ensure_admin_superuser, sender=self)

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("wo_pin_ge_dou")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

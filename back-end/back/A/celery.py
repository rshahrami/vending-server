import os
from celery import Celery
from celery.schedules import crontab
from .celery import app

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'A.settings')

app = Celery('A')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'update-protected-phone-cache-every-6-hours': {
        'task': 'myapp.tasks.update_protected_phone_cache',
        'schedule': 6 * 60 * 60,  # هر 6 ساعت
    },
}

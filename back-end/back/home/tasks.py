from celery import shared_task
from django.core.cache import cache
from home.models import ProtectedPhoneNumber

CACHE_KEY = "protected_phone_numbers"
CACHE_TIMEOUT = 6 * 60 * 60  # 6 ساعت بر حسب ثانیه

@shared_task
def update_protected_phone_cache():
    phone_numbers = list(ProtectedPhoneNumber.objects.values_list('phone_number', flat=True))
    # ذخیره در Redis cache
    cache.set(CACHE_KEY, phone_numbers, timeout=CACHE_TIMEOUT)
    print(f"Phone cache updated: {len(phone_numbers)} numbers")
    return len(phone_numbers)

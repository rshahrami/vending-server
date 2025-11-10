# devices/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from .models import Device

@receiver(post_delete, sender=Token)
def clear_device_name_on_token_delete(sender, instance, **kwargs):
    try:
        device = Device.objects.get(device_token=instance)
        device.device_name = ""
        device.device_token = None
        device.save()
    except Device.DoesNotExist:
        pass

from django import forms
# from django.contrib import admin
from rest_framework.authtoken.models import Token
from .models import Device

class DeviceForm(forms.ModelForm):
    # این فیلد فقط برای انتخاب توکن است
    device_token_field = forms.ModelChoiceField(
        queryset=Token.objects.all(),
        required=True,
        label="دستگاه"
    )

    class Meta:
        model = Device
        fields = ('device_id', 'device_phone_number', 'device_activity', 'device_token_field')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # مقدار اولیه برای ویرایش رکورد
        if self.instance and self.instance.device_token:
            self.fields['device_token_field'].initial = self.instance.device_token

        # نمایش نام نمایشی (FirstName LastName) در dropdown
        self.fields['device_token_field'].label_from_instance = lambda obj: f"{obj.user.first_name}" if obj.user else obj.key

    def save(self, commit=True):
        device = super().save(commit=False)
        token = self.cleaned_data['device_token_field']
        device.device_token = token
        # ذخیره username در device_name
        if token.user:
            device.device_name = token.user.username
        if commit:
            device.save()
        return device

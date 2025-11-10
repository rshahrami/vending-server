# -*- coding: utf-8 -*-
from django.contrib import admin
from django.http import HttpResponse
import pandas as pd
from home.models import Product, Device, RowData, TemproryData, Report, ProtectedPhoneNumber
from home.forms import DeviceForm
import jdatetime
from pytz import timezone
import datetime

# تابع تبدیل تاریخ میلادی به شمسی
def convert_to_jalali(gregorian_date):
    if gregorian_date:
        # تبدیل به وقت تهران
        tehran_tz = timezone('Asia/Tehran')
        localized_date = gregorian_date.astimezone(tehran_tz)
        
        # تبدیل به تاریخ شمسی
        jalali_date = jdatetime.datetime.fromgregorian(
            year=localized_date.year,
            month=localized_date.month,
            day=localized_date.day,
            hour=localized_date.hour,
            minute=localized_date.minute,
            second=localized_date.second
        )
        return jalali_date.strftime('%Y/%m/%d %H:%M:%S')
    return ""

# تابع کمکی برای export به اکسل
def export_to_excel(modeladmin, request, queryset):
    # ایجاد یک DataFrame از queryset
    data = []
    
    # اگر queryset خالی باشد، همه داده‌ها را export کن
    if not queryset:
        queryset = modeladmin.model.objects.all()
    
    for obj in queryset:
        row = {}
        for field in modeladmin.list_display:
            if hasattr(obj, field):
                value = getattr(obj, field)
                # اگر تابع باشد، فراخوانی کن
                if callable(value):
                    value = value()
                # اگر تاریخ باشد، به شمسی تبدیل کن
                if isinstance(value, (datetime.datetime, datetime.date)):
                    value = convert_to_jalali(value) if isinstance(value, datetime.datetime) else jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d')
                row[field] = str(value)
            else:
                # برای توابع تعریف شده در admin
                if hasattr(modeladmin, field):
                    method = getattr(modeladmin, field)
                    value = method(obj)
                    # اگر تاریخ باشد، به شمسی تبدیل کن
                    if isinstance(value, (datetime.datetime, datetime.date)):
                        value = convert_to_jalali(value) if isinstance(value, datetime.datetime) else jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d')
                    row[field] = str(value)
                else:
                    row[field] = ""
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # ایجاد پاسخ HTTP با فایل اکسل
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model.__name__}_export.xlsx"'
    
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Export')
    
    return response

export_to_excel.short_description = "خروجی اکسل از موارد انتخاب شده"

# کلاس‌های Admin با قابلیت export و فیلتر و تاریخ شمسی
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name')
    list_filter = ('product_id', 'product_name')
    search_fields = ('product_id', 'product_name')
    actions = [export_to_excel]

class DeviceAdmin(admin.ModelAdmin):
    form = DeviceForm
    list_display = ('device_id', 'display_name', 'device_phone_number', 'device_activity', 'device_token')
    list_filter = ('device_id', 'device_name', 'device_activity')
    search_fields = ('device_id', 'device_name', 'device_phone_number')
    actions = [export_to_excel]

class RowDataAdmin(admin.ModelAdmin):
    list_display = ('full_phone_number', 'device_display_name', 'product_id', 'jalali_datetime_created')
    list_filter = ('device_id', 'product_id', 'datetime_created')
    search_fields = ('phone_number', 'device_id__device_name', 'product_id__product_name')
    date_hierarchy = 'datetime_created'
    actions = [export_to_excel]

    def device_display_name(self, obj):
        if obj.device_id:
            return obj.device_id.display_name  # از property Device استفاده می‌کنیم
        return "-"
    device_display_name.short_description = "نام دستگاه"

    def full_phone_number(self, obj):
        return '0' + str(obj.phone_number)
    full_phone_number.short_description = 'شماره تلفن کامل'
    
    def jalali_datetime_created(self, obj):
        return convert_to_jalali(obj.datetime_created)
    jalali_datetime_created.short_description = 'تاریخ و زمان ایجاد (شمسی)'

class TemproryDataAdmin(admin.ModelAdmin):
    list_display = ('full_phone_number', 'gift_number')
    list_filter = ('gift_number',)
    search_fields = ('phone_number', 'gift_number')
    actions = [export_to_excel]

    def full_phone_number(self, obj):
        return '0' + str(obj.phone_number)
    full_phone_number.short_description = 'شماره تلفن کامل'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['device_display_name', 'report', 'jalali_datetime']
    list_filter = ['device_id', 'datetime']
    search_fields = ['report', 'device_id__device_name']
    readonly_fields = ['datetime']
    date_hierarchy = 'datetime'
    actions = [export_to_excel]

    def device_display_name(self, obj):
        if obj.device_id:
            return obj.device_id.display_name  # از property Device استفاده می‌کنیم
        return "-"
    device_display_name.short_description = "نام دستگاه"

    def jalali_datetime(self, obj):
        return convert_to_jalali(obj.datetime)
    jalali_datetime.short_description = 'تاریخ و زمان (شمسی)'



@admin.register(ProtectedPhoneNumber)
class ProtectedPhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('full_phone_number', 'jalali_datetime_created')
    list_filter = ('datetime_created',)
    search_fields = ('phone_number',)
    date_hierarchy = 'datetime_created'
    actions = [export_to_excel]

    def full_phone_number(self, obj):
        return '0' + str(obj.phone_number)
    full_phone_number.short_description = 'شماره تلفن کامل'
    
    def jalali_datetime_created(self, obj):
        return convert_to_jalali(obj.datetime_created)
    jalali_datetime_created.short_description = 'تاریخ ایجاد (شمسی)'

# ثبت مدل‌ها
admin.site.register(Product, ProductAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(RowData, RowDataAdmin)
admin.site.register(TemproryData, TemproryDataAdmin)
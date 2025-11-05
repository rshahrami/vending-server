from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import User

class UserAdminSuper(UserAdmin):
    pass
 
    # UserAdmin.fieldsets[2][1]['fields'] = (
    #     "is_active",
    #     "is_staff",
    #     "is_superuser",
    #     # 'is_author',
    #     'is_special',
    #     'is_special_time',
    #     "groups",
    #     "user_permissions",
    # )

    # UserAdmin.list_display += (
    #     "is_active",
    #     "is_superuser",
    #     'is_special_time_user',
    #     'list_special',
        
    #     # "is_staff",
    #     # "is_superuser",
    #     # 'is_author',
    # )



admin.site.register(User, UserAdminSuper)
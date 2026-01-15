from django.contrib import admin
from django.contrib.auth import get_user_model
from user.models import UserSocialAccount


# Register your models here.
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "display_name", "date_joined")
    list_filter = ("date_joined",)
    search_fields = ("username", "email", "display_name")
    ordering = ("-date_joined",)


admin.site.register(get_user_model(), UserAdmin)


class UserSocialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "provider",
        "subject",
        "email",
        "email_verified",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__username", "user__email", "subject", "email")
    ordering = ("-created_at", "updated_at")


admin.site.register(UserSocialAccount, UserSocialAccountAdmin)

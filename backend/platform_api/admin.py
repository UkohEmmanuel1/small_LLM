from django.contrib import admin
from .models import APIKey, Conversation, Message

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display=('name','user','prefix','created_at','last_used_at','revoked_at')
    readonly_fields=('key_hash','prefix','created_at','last_used_at')
admin.site.register(Conversation)
admin.site.register(Message)

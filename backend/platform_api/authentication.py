from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from .models import APIKey

class ProjectAPIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header=get_authorization_header(request).decode('utf-8').strip()
        if not header.startswith('Bearer sk-small-'):
            return None
        raw=header.removeprefix('Bearer ').strip()
        try: key=APIKey.objects.select_related('user').get(prefix=raw[:16],key_hash=APIKey.digest(raw),revoked_at__isnull=True)
        except APIKey.DoesNotExist: raise AuthenticationFailed('Invalid or revoked API key.')
        APIKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.user,key)

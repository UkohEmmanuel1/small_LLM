from rest_framework.authtoken.models import Token
from rest_framework.permissions import BasePermission

class IsAccountTokenUser(BasePermission):
    message = "A user account token is required for this operation."
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and isinstance(request.auth, Token))

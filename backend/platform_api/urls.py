from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .auth_views import RegisterView
from .key_views import APIKeyListCreateView, APIKeyRevokeView
from .public_views import PublicPlaygroundView

urlpatterns = [
    path("chat/", PublicPlaygroundView.as_view(), name="public-chat"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", obtain_auth_token, name="obtain-token"),
    path("keys/", APIKeyListCreateView.as_view(), name="api-keys"),
    path("keys/<int:pk>/", APIKeyRevokeView.as_view(), name="api-key-revoke"),
]

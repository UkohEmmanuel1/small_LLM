from django.urls import path
from .key_views import APIKeyListCreateView,APIKeyRevokeView
from .public_views import PublicPlaygroundView
urlpatterns=[
 path('chat/',PublicPlaygroundView.as_view(),name='public-chat'),
 path('keys/',APIKeyListCreateView.as_view(),name='api-keys'),
 path('keys/<int:pk>/',APIKeyRevokeView.as_view(),name='api-key-revoke'),
]

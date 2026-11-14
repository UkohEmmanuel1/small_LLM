from rest_framework import permissions
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle
from .views import ChatCompletionsView

class PublicPlaygroundView(ChatCompletionsView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "inference"

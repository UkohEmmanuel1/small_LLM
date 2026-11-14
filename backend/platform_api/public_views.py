from rest_framework import permissions
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from .views import ChatCompletionsView

class PublicPlaygroundView(ChatCompletionsView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "inference"

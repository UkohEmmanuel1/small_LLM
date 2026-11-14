from rest_framework import permissions
from rest_framework.throttling import AnonRateThrottle
from .views import ChatCompletionsView

class PublicPlaygroundView(ChatCompletionsView):
 permission_classes=[permissions.AllowAny]
 authentication_classes=[]
 throttle_classes=[AnonRateThrottle]

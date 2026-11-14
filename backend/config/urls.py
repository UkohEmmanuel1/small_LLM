from django.contrib import admin
from django.urls import path, include
from platform_api.views import HealthView, ModelsView, ChatCompletionsView, ConversationListCreateView, ConversationDetailView

urlpatterns = [
 path('admin/', admin.site.urls),
 path('api/health/', HealthView.as_view(), name='health'),
 path('v1/models', ModelsView.as_view(), name='models'),
 path('v1/chat/completions', ChatCompletionsView.as_view(), name='chat-completions'),
 path('api/conversations/', ConversationListCreateView.as_view(), name='conversations'),
 path('api/conversations/<int:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
 path('api/auth/', include('rest_framework.urls')),
]

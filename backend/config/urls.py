from django.contrib import admin
from django.urls import include, path
from platform_api.views import ChatCompletionsView, ConversationDetailView, ConversationListCreateView, HealthView, ModelsView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/", include("platform_api.urls")),
    path("api/conversations/", ConversationListCreateView.as_view(), name="conversations"),
    path("api/conversations/<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("v1/models", ModelsView.as_view(), name="models"),
    path("v1/chat/completions", ChatCompletionsView.as_view(), name="chat-completions"),
]

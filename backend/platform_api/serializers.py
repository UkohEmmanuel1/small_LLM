from rest_framework import serializers
from .models import Conversation, Message

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at", "messages"]
        read_only_fields = ["id", "created_at", "updated_at", "messages"]

class ChatMessageInputSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["system", "user", "assistant"])
    content = serializers.CharField(allow_blank=False, trim_whitespace=True, max_length=12000)

class ChatCompletionInputSerializer(serializers.Serializer):
    model = serializers.CharField(required=False, allow_blank=False, max_length=120)
    messages = ChatMessageInputSerializer(many=True, allow_empty=False, max_length=40)
    max_tokens = serializers.IntegerField(required=False, min_value=1, max_value=8192, default=512)
    temperature = serializers.FloatField(required=False, min_value=0.0, max_value=2.0, default=0.7)
    conversation_id = serializers.IntegerField(required=False, min_value=1)
    stream = serializers.BooleanField(required=False, default=False)

    def validate_messages(self, messages):
        if sum(len(item["content"]) for item in messages) > 24000:
            raise serializers.ValidationError("Combined prompt content exceeds the 24,000-character limit.")
        if not any(item["role"] == "user" for item in messages):
            raise serializers.ValidationError("At least one user message is required.")
        return messages

    def validate_stream(self, value):
        if value:
            raise serializers.ValidationError("Streaming is not enabled yet. Send stream=false.")
        return value

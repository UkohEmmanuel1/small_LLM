import hashlib
import secrets
from django.conf import settings
from django.db import models

class APIKey(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='api_keys')
    name=models.CharField(max_length=80)
    prefix=models.CharField(max_length=16,db_index=True)
    key_hash=models.CharField(max_length=64,unique=True)
    created_at=models.DateTimeField(auto_now_add=True)
    last_used_at=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    @staticmethod
    def digest(raw): return hashlib.sha256(raw.encode()).hexdigest()
    @classmethod
    def issue(cls,user,name='Default key'):
        raw='sk-small-'+secrets.token_urlsafe(32)
        return cls.objects.create(user=user,name=name,prefix=raw[:16],key_hash=cls.digest(raw)),raw
    def __str__(self): return f'{self.name} ({self.prefix}...)'

class Conversation(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='conversations')
    title=models.CharField(max_length=160,default='New conversation')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-updated_at']

class Message(models.Model):
    ROLE_CHOICES=[('system','System'),('user','User'),('assistant','Assistant')]
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages')
    role=models.CharField(max_length=12,choices=ROLE_CHOICES)
    content=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at']

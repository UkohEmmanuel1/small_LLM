from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
 initial=True
 dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
 operations=[
  migrations.CreateModel(name='APIKey',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=80)),('prefix',models.CharField(db_index=True,max_length=16)),('key_hash',models.CharField(max_length=64,unique=True)),('created_at',models.DateTimeField(auto_now_add=True)),('last_used_at',models.DateTimeField(blank=True,null=True)),('revoked_at',models.DateTimeField(blank=True,null=True)),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='api_keys',to=settings.AUTH_USER_MODEL))]),
  migrations.CreateModel(name='Conversation',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('title',models.CharField(default='New conversation',max_length=160)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='conversations',to=settings.AUTH_USER_MODEL))],options={'ordering':['-updated_at']}),
  migrations.CreateModel(name='Message',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('role',models.CharField(choices=[('system','System'),('user','User'),('assistant','Assistant')],max_length=12)),('content',models.TextField()),('created_at',models.DateTimeField(auto_now_add=True)),('conversation',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='messages',to='platform_api.conversation'))],options={'ordering':['created_at']}),
 ]

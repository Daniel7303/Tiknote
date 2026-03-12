from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

class UserProfile(models.Model):
    SYNC_OPTION= [
        ('auto', 'Auto-sync new videos'),
        ('manual', 'Manual-sync new only'),   
    ]
    
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    profile_image = models.URLField(max_length=500, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    tiktok_user_id = models.CharField(max_length=255, blank=True, null=True)
    union_id = models.CharField(max_length=255, blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token= models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    scope = models.CharField(max_length=255, blank=True, null=True)
    sync_preference = models.CharField(max_length=10, choices=SYNC_OPTION, default='auto')
    last_synced = models.DateTimeField(blank=True, null=True)
    
    def is_token_expired(self) -> bool:
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at
    
    
    
    
    def should_auto_sync(self):
        return self.sync_preference == 'auto'
    
    def mark_synced(self):
        self.last_synced = timezone.now()
        self.save(update_fields=['last_synced'])
        
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    
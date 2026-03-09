from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets

# Create your models here.


class OAuthState(models.Model):
    state = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'oauth_states'
        indexes = [
            models.Index(fields=['state', 'created_at']),
        ]
    
    @classmethod
    def create_state(cls):
        """Generate a new state token and save to database"""
        state = secrets.token_urlsafe(16)
        cls.objects.create(state=state)
        
        # Clean up old states (older than 10 minutes)
        cls.cleanup_old_states()
        
        return state
    
    @classmethod
    def verify_and_consume_state(cls, state):
        """Verify state exists and is valid, then delete it (one-time use)"""
        if not state:
            return False
        
        try:
            # Check if state exists and was created within last 10 minutes
            obj = cls.objects.get(
                state=state,
                created_at__gte=timezone.now() - timedelta(minutes=10)
            )
            obj.delete()  # Delete after verification (one-time use)
            return True
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def cleanup_old_states(cls):
        """Remove states older than 10 minutes"""
        cls.objects.filter(
            created_at__lt=timezone.now() - timedelta(minutes=10)
        ).delete()
    
    def __str__(self):
        return f"OAuth State: {self.state[:10]}... (created: {self.created_at})"
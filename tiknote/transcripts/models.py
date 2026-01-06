from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
from django.utils.text import slugify

class Video(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    video_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    share_url = models.URLField(blank=True)
    cover_image = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_transcribed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title or 'Untitled'} ({self.video_id})"

    def should_delete(self):
        """
        Delete video 1 hour after transcription completion.
        """
        if self.is_transcribed:
            return timezone.now() > self.created_at + timedelta(hours=1)
        return False



class Transcription(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transcriptions")
    video_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    transcript = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    slug = models.SlugField(null=True, blank=True)

    # Keep the thumbnail for visual context (optional)
    thumbnail_url = models.URLField(blank=True, null=True)
    
    # Temporary video path (gets deleted after transcription)
    temp_video_path = models.CharField(max_length=255, blank=True, null=True)

    def mark_completed(self, text):
        self.transcript = text
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()
        
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.title or self.video_id}"
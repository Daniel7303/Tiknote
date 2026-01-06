from django.db import models
from django.conf import settings

class Like(models.Model):
    """Likes on transcriptions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')
    transcription = models.ForeignKey('transcripts.Transcription', on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'transcription')  # One like per user per transcription
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes {self.transcription.title}"


class Comment(models.Model):
    """Comments on transcriptions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    transcription = models.ForeignKey('transcripts.Transcription', on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    text = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.text[:50]}"
    
    def get_replies(self):
        return self.replies.all().order_by('created_at')
    
    def is_reply(self):
        return self.parent is not None
    
    

class Bookmark(models.Model):
    """Bookmarks/Saves on transcriptions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    transcription = models.ForeignKey('transcripts.Transcription', on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'transcription')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} bookmarked {self.transcription.title}"

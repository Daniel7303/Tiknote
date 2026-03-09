# profiles/signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from accounts.tiktok_client import TikTokClient

@receiver(user_logged_in)
def auto_sync_on_login(sender, user, request, **kwargs):
    profile = getattr(user, 'profile', None)
    if profile and profile.should_auto_sync():
        client = TikTokClient(user)
        client.sync_new_videos()

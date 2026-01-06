from django.shortcuts import render, redirect
import requests
from django.http import HttpResponse, Http404
from django.views.decorators.cache import cache_page
from django.shortcuts import get_object_or_404

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserProfileForm
from django.utils import timezone
from accounts.tiktok_client import TikTokClient
from transcripts.models import Transcription
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Value
from transcripts.models import Transcription
from interactions.models import Like, Comment, Bookmark

# Create your views here.




@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profiles:profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'profiles/profile.html', {'form': form, 'profile': profile})


@login_required
def sync_now(request):
    """Manual sync trigger"""
    profile = request.user.profile
    tiktok_client = TikTokClient(request.user)
    
    try:
        synced_videos = tiktok_client.sync_new_videos()  # implement this in tiktok_client.py
        profile.mark_synced()
        messages.success(request, f"Synced {len(synced_videos)} new videos successfully.")
    except Exception as e:
        messages.error(request, f" Sync failed: {str(e)}")
    
    return redirect('profiles:profile')




@login_required
def transcriptions_page(request):
    """
    Display all user transcriptions.
    Completed ones are auto-deleted after 24 hours.
    """
    # Auto-clean old completed transcriptions
    # Transcription.objects.filter(
    #     user=request.user,
    #     status="completed",
    #     completed_at__lt=timezone.now() - timedelta(hours=24)
    # ).delete()

    # Fetch user transcriptions
    transcriptions = Transcription.objects.filter(user=request.user).order_by("-created_at").annotate(
        likes_count=Count('likes'),
        comments_count=Count('comments'),
        user_has_liked=Exists(
            Like.objects.filter(
                transcription=OuterRef('pk'),
                user=request.user
            )
        ) if request.user.is_authenticated else Value(False),
        user_has_bookmarked=Exists(
            Bookmark.objects.filter(
                transcription=OuterRef('pk'),
                user=request.user
            )
        ) if request.user.is_authenticated else Value(False)
    ).select_related('user', 'user__profile').order_by('?')
    

    return render(request, "profiles/profile_feed.html", {
        "transcriptions": transcriptions,
    })
    


# profiles/views.py
import requests
from django.http import HttpResponse, Http404
from django.views.decorators.cache import cache_page
from django.shortcuts import get_object_or_404
from profiles.models import UserProfile

@cache_page(60 * 60 * 24)  # Cache for 24 hours
def avatar_proxy(request, user_id):
    """Proxy TikTok avatar images"""
    try:
        profile = get_object_or_404(UserProfile, user_id=user_id)
        
        if not profile.avatar_url:
            raise Http404("No avatar URL")
        
        # Fetch the image from TikTok
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(
            profile.avatar_url, 
            headers=headers,
            timeout=10,
            allow_redirects=True
        )
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', 'image/jpeg')
            return HttpResponse(response.content, content_type=content_type)
        
        raise Http404("Image not found")
        
    except Exception as e:
        raise Http404(f"Error loading avatar: {str(e)}")
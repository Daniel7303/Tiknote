import logging
import urllib.parse
from datetime import timedelta
from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
import requests
from django.contrib.auth import login, logout, get_user_model
from django.core.exceptions import ValidationError
from profiles.models import UserProfile
from accounts.models import OAuthState
from .tiktok_client import refresh_tiktok_token
from transcripts.tasks import create_and_process_from_tiktok_video
from django.contrib import messages
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
import re

User = get_user_model()
logger = logging.getLogger(__name__)

# Constants
TIKTOK_AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
MAX_VIDEO_SELECTION = 10  # Limit bulk operations


def validate_video_id(video_id):
    """Validate TikTok video ID format"""
    if not video_id:
        return False
    # TikTok video IDs are typically 19 digits
    if not re.match(r'^\d{10,20}$', str(video_id)):
        return False
    return True


def sanitize_string(text, max_length=500):
    """Sanitize user input"""
    if not text:
        return ""
    text = str(text).strip()
    # Remove any null bytes
    text = text.replace('\x00', '')
    return text[:max_length]


@ratelimit(key='ip', rate='5/m', method='GET')
def tiktok_login(request):
    """Initiate TikTok OAuth flow"""
    client_key = settings.TIKTOK_CLIENT_KEY
    redirect_uri = settings.TIKTOK_REDIRECT_URI
    
    scope = "user.info.basic,user.info.profile,user.info.stats,video.list"
    
    # Generate secure state token
    state = OAuthState.create_state()
    
    auth_url = (
        f"{TIKTOK_AUTH_BASE}"
        f"?client_key={client_key}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&state={state}"
    )
    
    # ✅ SECURITY: Don't log sensitive data
    logger.info(f"TikTok OAuth initiated for IP: {request.META.get('REMOTE_ADDR')}")
    
    return redirect(auth_url)


@ratelimit(key='ip', rate='5/m', method='GET')
@csrf_protect
def tiktok_callback(request):
    """Handle TikTok OAuth callback"""
    code = request.GET.get("code", "").strip()
    state = request.GET.get("state", "").strip()
    error = request.GET.get("error", "").strip()
    
    if error:
        logger.warning(f"TikTok OAuth error: {error}")
        messages.error(request, "TikTok login failed. Please try again.")
        return redirect("accounts:tiktok_login")
    
    if not code or not state:
        logger.warning("Missing OAuth parameters")
        messages.error(request, "Invalid login request.")
        return redirect("accounts:tiktok_login")
    
    if not OAuthState.verify_and_consume_state(state):
        logger.warning("Invalid OAuth state")
        messages.error(request, "This login link has expired. Please try again.")
        return redirect("accounts:tiktok_login")
    
    # Exchange code for token
    data = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
    }
    
    try:
        response = requests.post(
            TIKTOK_TOKEN_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        token_data = response.json()
        
        if response.status_code != 200 or "access_token" not in token_data:
            logger.error(f"Token exchange failed")
            messages.error(request, "Authentication failed. Please try again.")
            return redirect("accounts:tiktok_login")
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 86400)
        open_id = token_data.get("open_id")
        
        if not open_id:
            logger.error("No open_id received")
            messages.error(request, "Authentication failed.")
            return redirect("accounts:tiktok_login")
        
        # Fetch user info with multiple avatar field options
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "fields": "open_id,union_id,avatar_url,avatar_url_100,avatar_large_url,display_name,username"
        }
        
        user_info_res = requests.get(
            "https://open.tiktokapis.com/v2/user/info/",
            headers=headers,
            params=params,
            timeout=30
        )
        user_info = user_info_res.json()
        
        # Debug logging
        logger.info(f"TikTok API Response Status: {user_info_res.status_code}")
        logger.info(f"TikTok User Info: {user_info}")
        
        if "data" not in user_info or "user" not in user_info["data"]:
            logger.warning("Failed to fetch user info")
            user_data = {
                "display_name": f"TikTokUser_{open_id[:8]}",
                "open_id": open_id,
                "avatar_url": None,
                "union_id": None
            }
        else:
            user_data = user_info["data"]["user"]
            logger.info(f"User data keys: {user_data.keys()}")
        
        # Extract data with fallbacks
        display_name = sanitize_string(
            user_data.get("display_name") or user_data.get("username") or f"TikTokUser_{open_id[:8]}",
            max_length=100
        )
        
        # Try multiple avatar field names
        avatar_url = (
            user_data.get("avatar_url") or 
            user_data.get("avatar_url_100") or 
            user_data.get("avatar_large_url") or 
            user_data.get("avatarUrl") or
            None
        )
        
        logger.info(f"Extracted avatar_url: {avatar_url}")
        
        tiktok_user_id = user_data.get("open_id") or open_id
        union_id = user_data.get("union_id")
        
        # Validate avatar URL
        if avatar_url:
            if not avatar_url.startswith(('http://', 'https://')):
                logger.warning(f"Invalid avatar URL format: {avatar_url}")
                avatar_url = None
            else:
                logger.info(f"Valid avatar URL: {avatar_url}")
        else:
            logger.warning("No avatar URL found in TikTok response")
        
        # Create or get user
        user, created = User.objects.get_or_create(
            username=tiktok_user_id[:150]
        )
        
        if created or not user.first_name:
            user.first_name = display_name
            user.save()
        
        # Update profile
        profile, profile_created = UserProfile.objects.get_or_create(user=user)
        profile.tiktok_user_id = tiktok_user_id
        profile.access_token = access_token
        profile.refresh_token = refresh_token
        profile.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        profile.scope = "user.info.basic,user.info.profile,user.info.stats,video.list"
        profile.last_synced = timezone.now()
        profile.display_name = display_name
        profile.union_id = union_id
        
        # Explicitly set avatar_url (even if None for now)
        profile.avatar_url = avatar_url
        
        # Also save to profile_image as backup
        if avatar_url:
            profile.profile_image = avatar_url
        
        profile.save()
        
        logger.info(f"Profile saved - Avatar URL in DB: {profile.avatar_url}")
        logger.info(f"Profile ID: {profile.id}, User: {user.username}")
        
        # Log in the user
        login(request, user)
        messages.success(request, f"Welcome, {display_name}!")
        
        return redirect("feeds:main-feeds")
        
    except Exception as e:
        logger.error(f"Error during OAuth: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred. Please try again.")
        return redirect("accounts:tiktok_login")


@login_required
@require_http_methods(["GET", "POST"])
def tiktok_disconnect(request):
    """Disconnect TikTok account and logout"""
    # ✅ SECURITY: Clear sensitive data
    try:
        profile = UserProfile.objects.get(user=request.user)
        profile.access_token = None
        profile.refresh_token = None
        profile.token_expires_at = None
        profile.save()
    except UserProfile.DoesNotExist:
        pass
    
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("feeds:main-feeds")


@login_required
@ratelimit(key='user', rate='20/m', method='GET')
def sync_videos_page(request):
    """Fetch TikTok videos for the authenticated user."""
    profile = UserProfile.objects.filter(user=request.user).first()
    
    if not profile or not profile.access_token:
        messages.error(request, "Please reconnect TikTok.")
        return redirect("accounts:tiktok_login")
    
    # Refresh token if expired
    if not refresh_tiktok_token(profile):
        messages.error(request, "Your TikTok token has expired. Please reconnect.")
        return redirect("accounts:tiktok_login")
    
    headers = {
        "Authorization": f"Bearer {profile.access_token}",
        "Content-Type": "application/json",
    }

    params = {
        "fields": "id,title,video_description,duration,cover_image_url,share_url,create_time"
    }
    
    payload = {
        "max_count": 20,
        "cursor": 0
    }
    
    try:
        logger.info(f"Fetching TikTok videos for user {request.user.id}")
        
        response = requests.post(
            TIKTOK_VIDEO_LIST_URL,
            json=payload,
            params=params,
            headers=headers,
            timeout=30
        )
        
        logger.info(f"TikTok API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"TikTok API error: {response.status_code}")
            messages.error(request, "Failed to fetch videos from TikTok.")
            return render(request, "accounts/sync_videos.html", {"videos": []})
        
        if not response.text:
            messages.error(request, "Empty response from TikTok.")
            return render(request, "accounts/sync_videos.html", {"videos": []})
        
        try:
            data = response.json()
        except ValueError:
            logger.error("Invalid JSON response from TikTok")
            messages.error(request, "Invalid response from TikTok.")
            return render(request, "accounts/sync_videos.html", {"videos": []})
        
        # Check for API errors
        if "error" in data:
            error_info = data["error"]
            error_code = error_info.get("code", "")
            
            if error_code and error_code != "ok":
                logger.error(f"TikTok API error code: {error_code}")
                messages.error(request, "TikTok API error. Please try again.")
                return render(request, "accounts/sync_videos.html", {"videos": []})
        
        # Extract videos
        videos = data.get("data", {}).get("videos", [])
        
        # ✅ SECURITY: Validate video data
        validated_videos = []
        for video in videos:
            if validate_video_id(video.get("id")):
                # Sanitize title and description
                video['title'] = sanitize_string(video.get('title', ''), max_length=200)
                video['video_description'] = sanitize_string(
                    video.get('video_description', ''), 
                    max_length=500
                )
                validated_videos.append(video)
        
        if not validated_videos:
            logger.info("No valid videos found")
            messages.warning(request, "No videos found. Make sure you have public videos on TikTok.")
        else:
            logger.info(f"Successfully fetched {len(validated_videos)} videos")
            messages.success(request, f"Found {len(validated_videos)} videos!")
        
        return render(request, "accounts/sync_videos.html", {"videos": validated_videos})
        
    except requests.Timeout:
        logger.error("TikTok API timeout")
        messages.error(request, "Request timed out. Please try again.")
        return render(request, "accounts/sync_videos.html", {"videos": []})
        
    except requests.RequestException as e:
        logger.error(f"TikTok API request failed: {type(e).__name__}")
        messages.error(request, "Failed to connect to TikTok.")
        return render(request, "accounts/sync_videos.html", {"videos": []})
        
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}", exc_info=True)
        messages.error(request, "An error occurred.")
        return render(request, "accounts/sync_videos.html", {"videos": []})


@login_required
@require_POST
@ratelimit(key='user', rate='10/m', method='POST')
def enqueue_selected_videos(request):
    """Enqueue selected TikTok videos for transcription."""
    selected_videos = request.POST.getlist("video_id")
    
    if not selected_videos:
        messages.warning(request, "No videos selected.")
        return redirect("accounts:sync_videos_page")
    
    # ✅ SECURITY: Limit bulk operations
    if len(selected_videos) > MAX_VIDEO_SELECTION:
        messages.error(request, f"You can only select up to {MAX_VIDEO_SELECTION} videos at once.")
        return redirect("accounts:sync_videos_page")
    
    user = request.user
    queued_count = 0
    failed = []
    
    for video_id in selected_videos:
        # ✅ SECURITY: Validate video ID
        if not validate_video_id(video_id):
            logger.warning(f"Invalid video ID attempted: {video_id[:20]}")
            failed.append(video_id)
            continue
        
        try:
            # Queue the video for transcription
            create_and_process_from_tiktok_video.delay(user.id, str(video_id))
            queued_count += 1
        except Exception as e:
            logger.error(f"Failed to enqueue video: {type(e).__name__}")
            failed.append(video_id)
    
    if queued_count:
        messages.success(request, f"✅ {queued_count} video(s) queued for transcription.")
    
    if failed:
        messages.error(request, f"❌ Failed to queue {len(failed)} video(s).")
    
    return redirect("accounts:transcriptions_page")


@login_required
@ratelimit(key='user', rate='30/m', method='GET')
def transcriptions_page(request):
    """Display all transcriptions for the authenticated user."""
    from transcripts.models import Transcription
    
    # ✅ SECURITY: Only show user's own transcriptions
    transcriptions = Transcription.objects.filter(
        user=request.user
    ).select_related('user').order_by('-created_at')
    
    # Separate by status
    pending = transcriptions.filter(status='pending')
    completed = transcriptions.filter(status='completed')
    failed = transcriptions.filter(status='failed')
    
    context = {
        'transcriptions': transcriptions,
        'pending': pending,
        'completed': completed,
        'failed': failed,
        'pending_count': pending.count(),
        'completed_count': completed.count(),
        'failed_count': failed.count(),
    }
    
    return render(request, 'accounts/transcriptions.html', context)

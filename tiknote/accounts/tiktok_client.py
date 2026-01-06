import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


from profiles.models import UserProfile
from transcripts.models import Video

logger = logging.getLogger(__name__)

TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"


# -------------------------------------
# 1️⃣ Helper: Refresh TikTok Access Token
# -------------------------------------
def refresh_tiktok_token(profile: UserProfile) -> bool:
    """
    Refresh user's TikTok access token if expired.
    Returns True if refreshed successfully, False otherwise.
    """
    if not profile.refresh_token:
        logger.warning("⚠️ No refresh token found for user.")
        return False

    if not profile.is_token_expired():
        logger.info("✅ Token still valid, no refresh needed.")
        return True

    logger.info("🔄 Token expired, refreshing...")

    data = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": profile.refresh_token,
    }

    try:
        response = requests.post(
            TIKTOK_TOKEN_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )

        token_data = response.json()
        logger.info(f"🎟️ Token Refresh Response: {token_data}")

        if "access_token" not in token_data:
            logger.error("❌ Failed to refresh token.")
            return False

        # Update tokens in DB
        profile.access_token = token_data["access_token"]
        profile.refresh_token = token_data.get("refresh_token", profile.refresh_token)
        profile.token_expires_at = timezone.now() + timedelta(seconds=token_data.get("expires_in", 86400))
        profile.save()

        logger.info(f"✅ Token refreshed successfully for user {profile.user.username}")
        return True

    except Exception as e:
        logger.error(f"Error refreshing TikTok token: {e}")
        return False


# -------------------------------------
# 2️⃣ Helper: TikTok API Request Wrapper
# -------------------------------------
def tiktok_api_request(profile: UserProfile, url: str, params=None, method="GET"):
    """
    Make authenticated requests to TikTok API using stored access token.
    Auto-refreshes expired tokens.
    """
    if not refresh_tiktok_token(profile):
        return {"error": "Failed to refresh TikTok token"}

    headers = {"Authorization": f"Bearer {profile.access_token}"}

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=10)
        else:
            response = requests.post(url, headers=headers, data=params, timeout=10)

        data = response.json()
        if response.status_code != 200:
            logger.warning(f"⚠️ TikTok API returned {response.status_code}: {data}")
        return data

    except requests.Timeout:
        logger.error("⏱️ TikTok API request timed out.")
        return {"error": "TikTok API request timed out"}

    except Exception as e:
        logger.error(f"TikTok API request failed: {e}")
        return {"error": str(e)}


# -------------------------------------
# 3️⃣ Fetch User Videos
# -------------------------------------
def get_user_videos(profile: UserProfile, page=1, page_size=20):
    """
    Fetch user's TikTok videos.
    """
    params = {
        "fields": "id,create_time,share_url,title,cover_image_url",
        "page_size": page_size,
        "cursor": (page - 1) * page_size,
    }

    logger.info(f"📹 Fetching TikTok videos for {profile.user.username} (page {page})")

    return tiktok_api_request(profile, TIKTOK_VIDEO_LIST_URL, params=params)


class TikTokClient:
    def __init__(self, user):
        self.user = user
        self.profile = getattr(user, 'profile', None)

        if not self.profile:
            raise Exception("User profile not found.")
        
        if not self.profile.access_token:
            raise Exception("No TikTok access token found for this user.")

    def sync_and_transcribe(self):
        """
        Fetch TikTok videos, transcribe them,
        then delete video records afterward.
        """
        videos = self.get_videos_from_tiktok()
        new_videos = []

        for v in videos:
            video_id = v.get("id")
            if not video_id:
                continue

            # Save temporarily
            video = Video.objects.create(
                user=self.user,
                video_id=video_id,
                title=v.get("title", ""),
                caption=v.get("caption", ""),
                share_url=v.get("share_url", ""),
                cover_image=v.get("cover_image_url", ""),
            )

            # Transcribe immediately
            transcript_text = self.transcribe_video(video)
            video.is_transcribed = True
            video.save()

            # Render to user or save transcript text elsewhere
            self.render_transcription(video, transcript_text)

            # Delete after transcription is done
            video.delete()
            new_videos.append(video_id)

        return {"synced": len(new_videos)}

    def transcribe_video(self, video):
        """
        Simulated transcription logic.
        Replace this with your actual processing code.
        """
        logger.info(f"🧠 Transcribing video {video.video_id}...")
        # Example placeholder:
        transcript_text = f"Transcript for video {video.title or video.video_id}"
        return transcript_text

    def render_transcription(self, video, text):
        """
        Render the transcript or send it to your frontend / feed.
        """
        logger.info(f"📝 Rendering transcript for {video.video_id}")
        # You can save the transcript to a NotePost, Article, or Transcript model.
        # Example:
        # Transcript.objects.create(user=self.user, video_id=video.video_id, text=text)


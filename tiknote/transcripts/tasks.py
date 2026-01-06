# from celery import shared_task
# import logging
# import requests
# import os
# from django.conf import settings
# from django.contrib.auth import get_user_model
# from transcripts.models import Transcription
# from transcripts.utils import transcribe_video  # ✅ Your Whisper function
# from profiles.models import UserProfile

# User = get_user_model()
# logger = logging.getLogger(__name__)

# @shared_task
# def create_and_process_from_tiktok_video(user_id, video_id):
#     """
#     Simple test task - will expand later
#     """
#     try:
#         logger.info(f"🎬 Task started for user {user_id}, video {video_id}")
        
#         # Import here to avoid circular imports
#         from transcripts.models import Transcription
        
#         user = User.objects.get(id=user_id)
        
#         # Create transcription record
#         transcription = Transcription.objects.create(
#             user=user,
#             video_id=video_id,
#             title=f"Video {video_id}",
#             status='pending'
#         )
        
#         logger.info(f"✅ Transcription record created: {transcription.id}")
        
#         # For now, just mark as completed with dummy text
#         # Later we'll add the actual download and Whisper transcription
#         import time
#         time.sleep(5)  # Simulate processing
        
#         transcription.mark_completed("This is a test transcript. Whisper integration coming next!")
        
#         logger.info(f"✅ Task completed for video {video_id}")
#         return f"Processed video {video_id}"
        
#     except Exception as e:
#         logger.error(f"❌ Task failed: {str(e)}", exc_info=True)
#         raise


# def get_video_info_from_tiktok(profile, video_id):
#     """
#     Fetch video details from TikTok API.
#     """
#     try:
#         from accounts.tiktok_client import refresh_tiktok_token
        
#         # Ensure token is valid
#         if not refresh_tiktok_token(profile):
#             logger.error("Failed to refresh TikTok token")
#             return None
        
#         # Query TikTok API for video details
#         url = "https://open.tiktokapis.com/v2/video/query/"
#         headers = {
#             "Authorization": f"Bearer {profile.access_token}",
#             "Content-Type": "application/json"
#         }
#         params = {
#             "fields": "id,title,video_description,duration,cover_image_url,download_url,share_url"
#         }
#         payload = {
#             "filters": {
#                 "video_ids": [video_id]
#             }
#         }
        
#         response = requests.post(url, json=payload, params=params, headers=headers, timeout=30)
        
#         if response.status_code == 200:
#             data = response.json()
#             videos = data.get('data', {}).get('videos', [])
#             if videos:
#                 return videos[0]
        
#         logger.error(f"Failed to fetch video info: {response.text}")
#         return None
        
#     except Exception as e:
#         logger.error(f"Error fetching video info: {e}")
#         return None


# def download_tiktok_video(video_url, video_id):
#     """
#     Download TikTok video to temporary file.
#     """
#     try:
#         # Create temp directory if it doesn't exist
#         temp_dir = os.path.join(settings.BASE_DIR, 'temp_videos')
#         os.makedirs(temp_dir, exist_ok=True)
        
#         temp_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
#         logger.info(f"📥 Downloading video from {video_url}")
        
#         # Download the video
#         response = requests.get(video_url, stream=True, timeout=60)
#         response.raise_for_status()
        
#         # Save to file
#         with open(temp_path, 'wb') as f:
#             for chunk in response.iter_content(chunk_size=8192):
#                 if chunk:
#                     f.write(chunk)
        
#         logger.info(f"✅ Video downloaded: {temp_path} ({os.path.getsize(temp_path)} bytes)")
#         return temp_path
        
#     except Exception as e:
#         logger.error(f"❌ Failed to download video: {e}")
#         return None

from celery import shared_task
import logging
import requests
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from transcripts.models import Transcription
from transcripts.utils import transcribe_video
from profiles.models import UserProfile
from accounts.tiktok_client import refresh_tiktok_token

User = get_user_model()
logger = logging.getLogger(__name__)

@shared_task
def create_and_process_from_tiktok_video(user_id, video_id):
    """
    Download TikTok video and transcribe it using Whisper.
    """
    temp_video_path = None
    
    try:
        user = User.objects.get(id=user_id)
        profile = UserProfile.objects.get(user=user)
        
        logger.info(f" Starting transcription for video {video_id}")
        
        # Refresh token if needed
        if not refresh_tiktok_token(profile):
            raise Exception("Failed to refresh TikTok token")
        
        # Get video details from TikTok API
        video_info = get_video_details(profile, video_id)
        
        # Create transcription record - moved outside try to ensure it's accessible
        transcription, created = Transcription.objects.get_or_create(
            user=user,
            video_id=video_id,
            defaults={
                'title': video_info.get('title', f'Video {video_id}'),
                'thumbnail_url': video_info.get('cover_image_url'),
                'status': 'pending'
            }
        )
        
        # If already exists and completed, skip
        if not created and transcription.status == 'completed':
            logger.info(f" Video {video_id} already transcribed, skipping")
            return f"Video {video_id} already transcribed"
        
        # Update to pending if it was failed before
        if transcription.status == 'failed':
            transcription.status = 'pending'
            transcription.save()
        
        logger.info(f" Transcription record: {transcription.id} (created={created})")
        
        # Download the video
        video_url = video_info.get('share_url')
        if not video_url:
            raise Exception("No video URL found")
        
        temp_video_path = download_video(video_url, video_id)
        
        if not temp_video_path or not os.path.exists(temp_video_path):
            raise Exception("Failed to download video")
        
        logger.info(f" Video downloaded: {temp_video_path}")
        
        # Transcribe using Whisper
        logger.info(f" Starting Whisper transcription...")
        transcript_text, language = transcribe_video(temp_video_path)
        
        logger.info(f" Transcription completed. Language: {language}, Length: {len(transcript_text)} chars")
        
        # Save the transcript
        transcription.mark_completed(transcript_text)
        
        # Clean up
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
            logger.info(f" Cleaned up: {temp_video_path}")
        
        return f"Successfully transcribed video {video_id}"
        
    except Exception as e:
        logger.error(f" Failed to transcribe video {video_id}: {str(e)}", exc_info=True)
        
        # Mark as failed - safely handle if transcription doesn't exist
        try:
            transcription = Transcription.objects.filter(
                user_id=user_id, 
                video_id=video_id
            ).first()
            
            if transcription:
                transcription.status = 'failed'
                transcription.save()
                logger.info(f"Marked transcription {transcription.id} as failed")
        except Exception as update_error:
            logger.error(f"Could not update transcription status: {update_error}")
        
        # Clean up on error
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                logger.info(f"🗑️ Cleaned up failed download: {temp_video_path}")
            except Exception as cleanup_error:
                logger.error(f"Could not clean up file: {cleanup_error}")
        
        raise


def get_video_details(profile, video_id):
    """
    Fetch video metadata from TikTok API.
    """
    try:
        # First try to get from video list endpoint
        url = "https://open.tiktokapis.com/v2/video/list/"
        headers = {
            "Authorization": f"Bearer {profile.access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "fields": "id,title,cover_image_url,share_url,video_description,duration"
        }
        payload = {
            "max_count": 20,
            "cursor": 0
        }
        
        response = requests.post(url, json=payload, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            videos = data.get('data', {}).get('videos', [])
            
            # Find our video
            for video in videos:
                if video.get('id') == video_id:
                    logger.info(f" Found video details: {video.get('title')}")
                    return video
        
        # If not found, return minimal info
        logger.warning(f" Could not fetch full video details, using minimal info")
        return {
            'id': video_id,
            'title': f'TikTok Video {video_id[:8]}',
            'cover_image_url': None,
            'share_url': f'https://www.tiktok.com/@user/video/{video_id}'
        }
        
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
        return {
            'id': video_id,
            'title': f'TikTok Video {video_id[:8]}',
            'share_url': f'https://www.tiktok.com/@user/video/{video_id}'
        }


def download_video(video_url, video_id):
    """
    Download TikTok video using yt-dlp.
    """
    try:
        import yt_dlp
        
        # Create temp directory
        temp_dir = os.path.join(settings.BASE_DIR, 'temp_videos')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        logger.info(f" Downloading video from {video_url}")
        
        # yt-dlp options
        ydl_opts = {
            'outtmpl': temp_path,
            'format': 'best',  # Download best quality
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            # Add cookies if needed for authentication
            'cookiefile': None,
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f" Starting download with yt-dlp...")
            ydl.download([video_url])
        
        # Verify file exists and has content
        if not os.path.exists(temp_path):
            raise Exception("Video file was not created")
        
        file_size = os.path.getsize(temp_path)
        logger.info(f" Video downloaded: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        if file_size < 1000:
            raise Exception("Downloaded file is too small")
        
        return temp_path
        
    except ImportError:
        logger.error(" yt-dlp not installed. Run: pip install yt-dlp")
        raise Exception("yt-dlp is required. Install with: pip install yt-dlp")
    except Exception as e:
        logger.error(f" Failed to download video: {e}")
        # Clean up partial download
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise
# import logging

# logger = logging.getLogger(__name__)

# def transcribe_video(video_path: str) -> tuple[str, str]:
#     """
#     Transcribe an audio/video file using OpenAI Whisper.
#     Returns a tuple: (transcript_text, detected_language)
#     """
#     try:
#         import whisper
#         logger.info(f" Starting Whisper transcription for {video_path}")
#         model = whisper.load_model("base")  # You can use "small" or "medium" for better accuracy

#         result = model.transcribe(video_path, fp16=False)
#         text = result.get("text", "").strip()
#         language = result.get("language", "unknown")

#         if not text:
#             raise ValueError("Whisper returned empty transcription text.")

#         logger.info(f" Transcription completed. Language: {language}")
#         return text, language

#     except Exception as e:
#         logger.error(f" Transcription failed: {e}")
#         raise RuntimeError(f"Transcription failed: {e}")



import requests
import logging
import os

logger = logging.getLogger(__name__)

def transcribe_video(video_path: str) -> tuple[str, str]:
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    headers = {"authorization": api_key}

    # Upload file
    with open(video_path, "rb") as f:
        upload_response = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=f
        )
    upload_url = upload_response.json()["upload_url"]

    # Request transcription
    transcript_response = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json={"audio_url": upload_url}
    )
    transcript_id = transcript_response.json()["id"]

    # Poll for completion
    import time
    while True:
        result = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=headers
        ).json()
        if result["status"] == "completed":
            return result["text"], result.get("language_code", "en")
        elif result["status"] == "error":
            raise RuntimeError(f"Transcription failed: {result['error']}")
        time.sleep(3)

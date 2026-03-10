import logging

logger = logging.getLogger(__name__)

def transcribe_video(video_path: str) -> tuple[str, str]:
    """
    Transcribe an audio/video file using OpenAI Whisper.
    Returns a tuple: (transcript_text, detected_language)
    """
    try:
        import whisper
        logger.info(f" Starting Whisper transcription for {video_path}")
        model = whisper.load_model("base")  # You can use "small" or "medium" for better accuracy

        result = model.transcribe(video_path, fp16=False)
        text = result.get("text", "").strip()
        language = result.get("language", "unknown")

        if not text:
            raise ValueError("Whisper returned empty transcription text.")

        logger.info(f" Transcription completed. Language: {language}")
        return text, language

    except Exception as e:
        logger.error(f" Transcription failed: {e}")
        raise RuntimeError(f"Transcription failed: {e}")

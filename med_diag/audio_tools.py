import io

def try_transcribe_audio(audio_bytes: bytes, api_key: str) -> str:
    if not audio_bytes:
        return ""

    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("Voice transcription requires the openai package.") from e

    client = OpenAI(api_key=api_key) if api_key.strip() else OpenAI()
    bio = io.BytesIO(audio_bytes)
    bio.name = "symptoms.wav"

    transcript = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=bio,
    )
    return str(transcript.text).strip()

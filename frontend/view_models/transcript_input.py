"""La transcripción que envía el operador: texto escrito o un archivo .txt subido."""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile
from django.http import QueryDict
from django.utils.datastructures import MultiValueDict

MIN_TRANSCRIPT_CHARS = 10
MAX_UPLOAD_BYTES = 200_000


class TranscriptInputError(ValueError):
    """La transcripción enviada (escrita o subida) no se puede analizar."""


def decode_text_upload(data: bytes) -> str:
    """Decodifica un archivo de texto subido: UTF-8 (con o sin BOM), si no Windows-1252."""
    if b"\x00" in data:
        raise TranscriptInputError("El archivo no parece ser de texto plano.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def transcript_from_submission(
    post: QueryDict, files: MultiValueDict[str, UploadedFile]
) -> str:
    """Resuelve la transcripción del formulario de carga. El archivo subido tiene prioridad sobre el texto escrito."""
    upload = files.get("transcript_file")
    if upload is not None and upload.size:
        if upload.size > MAX_UPLOAD_BYTES:
            raise TranscriptInputError(
                f"El archivo supera el máximo de {MAX_UPLOAD_BYTES // 1000} KB."
            )
        transcript = decode_text_upload(upload.read()).strip()
    else:
        transcript = (post.get("transcript") or "").strip()
    if len(transcript) < MIN_TRANSCRIPT_CHARS:
        raise TranscriptInputError("La transcripción es demasiado corta para analizar.")
    return transcript

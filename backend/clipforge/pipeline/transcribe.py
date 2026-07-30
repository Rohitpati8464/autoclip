"""Transcribe stage — audio to word-level timestamps.

faster-whisper does the transcription; WhisperX (optional) adds speaker labels.
Word-level timing is non-negotiable: clip boundaries, caption animation, and
trim-handle snapping all derive from it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from ..config import WhisperSettings
from ..system import GPUInfo, report
from .transcript import Segment, Transcript, Word

log = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """Transcription could not be completed."""


def resolve_compute(settings: WhisperSettings, gpu: GPUInfo | None = None) -> tuple[str, str]:
    """Return the ``(device, compute_type)`` to run Whisper with.

    An explicit ``settings.compute_type`` always wins — users debugging a
    numerical problem need to be able to force it.
    """
    gpu = gpu if gpu is not None else report().gpu
    compute_type = settings.compute_type or gpu.compute_type
    return gpu.device, compute_type


def transcribe(
    audio: Path,
    settings: WhisperSettings | None = None,
    *,
    duration_s: float | None = None,
    on_progress: Callable[[float], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Transcript:
    """Transcribe an audio file into a :class:`Transcript` with word timings.

    Preconditions:
        audio is a decodable audio file, ideally 16 kHz mono as produced by
        :func:`clipforge.pipeline.prepare.extract_audio`.
    """
    settings = settings or WhisperSettings()

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - faster-whisper is a core dep
        raise TranscriptionError(
            "faster-whisper is not installed. Run `clipforge doctor` for details."
        ) from exc

    device, compute_type = resolve_compute(settings)
    log.info(
        "Transcribing with model=%s device=%s compute_type=%s",
        settings.model,
        device,
        compute_type,
    )

    try:
        model = WhisperModel(settings.model, device=device, compute_type=compute_type)
    except Exception as exc:
        if device == "cuda":
            raise TranscriptionError(
                f"Could not load Whisper on the GPU ({exc}). This is usually a missing "
                "cuDNN runtime — install it with `uv pip install 'clipforge[gpu]'`, or "
                "force CPU by setting whisper.compute_type to 'int8' in config.json."
            ) from exc
        raise TranscriptionError(f"Could not load the Whisper model: {exc}") from exc

    segments_iter, info = model.transcribe(
        str(audio),
        language=settings.language or None,
        word_timestamps=True,
        vad_filter=True,
        # Trims long silences before decoding, which both speeds things up and
        # stops Whisper hallucinating text into empty audio.
        vad_parameters={"min_silence_duration_ms": 500},
    )

    total = duration_s or getattr(info, "duration", 0.0) or 0.0
    transcript = Transcript(
        language=getattr(info, "language", "") or settings.language,
        model=settings.model,
        source="whisper",
    )

    for segment in segments_iter:
        if cancelled is not None and cancelled():
            raise TranscriptionError("Transcription cancelled.")

        first_word = len(transcript.words)
        for word in getattr(segment, "words", None) or []:
            text = (word.word or "").strip()
            if not text:
                continue
            transcript.words.append(Word(text=text, start=float(word.start), end=float(word.end)))

        # A segment with no word timings still carries text worth keeping for
        # display, but it can't contribute to word-indexed clip boundaries.
        last_word = max(first_word, len(transcript.words) - 1)
        transcript.segments.append(
            Segment(
                text=(segment.text or "").strip(),
                start=float(segment.start),
                end=float(segment.end),
                first_word=first_word,
                last_word=last_word,
            )
        )

        if on_progress and total:
            on_progress(min(1.0, float(segment.end) / total))

    if not transcript.words:
        raise TranscriptionError(
            "No speech was detected in this audio. If the file really does contain "
            "speech, try a larger Whisper model or check that the correct audio track "
            "was extracted."
        )

    if on_progress:
        on_progress(1.0)

    log.info(
        "Transcribed %d words in %d segments.", len(transcript.words), len(transcript.segments)
    )
    return transcript


# --------------------------------------------------------------------------
# Diarization
# --------------------------------------------------------------------------


def diarize(
    audio: Path,
    transcript: Transcript,
    *,
    hf_token: str | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> Transcript:
    """Label each word with a speaker, in place.

    Uses pyannote via WhisperX. Returns the transcript unchanged (with a logged
    warning) if diarization isn't available — speaker labels improve reframing
    but are never required for the pipeline to complete.

    Preconditions:
        transcript already has word-level timings.
    """
    if not transcript.words:
        return transcript

    pipeline_cls = _load_diarization_pipeline()
    if pipeline_cls is None:
        log.warning(
            "WhisperX is not installed; skipping diarization. "
            "Install it with `uv pip install 'clipforge[diarization]'`."
        )
        return transcript

    if not hf_token:
        log.warning(
            "Diarization needs a HuggingFace token. Set one with "
            "`clipforge config set-secret huggingface_token`, and accept the pyannote "
            "model licences on huggingface.co. Continuing without speaker labels."
        )
        return transcript

    device = report().gpu.device
    try:
        pipeline = pipeline_cls(use_auth_token=hf_token, device=device)
        diarization = pipeline(str(audio), min_speakers=min_speakers, max_speakers=max_speakers)
    except Exception as exc:
        log.warning("Diarization failed (%s); continuing without speaker labels.", exc)
        return transcript

    turns = _diarization_turns(diarization)
    if not turns:
        return transcript

    _assign_speakers(transcript, turns)
    log.info("Diarization labelled %d speakers.", len(transcript.speakers))
    return transcript


def _load_diarization_pipeline():
    """Import WhisperX's diarization pipeline across its API reshuffles."""
    try:
        from whisperx.diarize import DiarizationPipeline

        return DiarizationPipeline
    except ImportError:
        pass
    try:
        from whisperx import DiarizationPipeline  # type: ignore[attr-defined]

        return DiarizationPipeline
    except (ImportError, AttributeError):
        return None


def _diarization_turns(diarization) -> list[tuple[str, float, float]]:
    """Normalise WhisperX output into ``(speaker, start, end)`` tuples.

    Recent versions return a pandas DataFrame; older ones return a pyannote
    ``Annotation``. Both are handled so the extra can be upgraded independently.
    """
    turns: list[tuple[str, float, float]] = []

    if hasattr(diarization, "itertuples"):  # DataFrame
        for row in diarization.itertuples():
            speaker = getattr(row, "speaker", None)
            start = getattr(row, "start", None)
            end = getattr(row, "end", None)
            if speaker is not None and start is not None and end is not None:
                turns.append((str(speaker), float(start), float(end)))
        return turns

    if hasattr(diarization, "itertracks"):  # pyannote Annotation
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            turns.append((str(speaker), float(segment.start), float(segment.end)))

    return turns


def _assign_speakers(transcript: Transcript, turns: list[tuple[str, float, float]]) -> None:
    """Attach a speaker to every word by maximum temporal overlap.

    Overlap rather than midpoint containment: words straddling a turn boundary
    are common, and the speaker who covers more of the word is the better guess.
    """
    turns = sorted(turns, key=lambda t: t[1])

    for word in transcript.words:
        best_speaker: str | None = None
        best_overlap = 0.0
        for speaker, start, end in turns:
            if start > word.end:
                break
            overlap = min(word.end, end) - max(word.start, start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        word.speaker = best_speaker

    for segment in transcript.segments:
        segment.speaker = transcript.dominant_speaker(segment.first_word, segment.last_word)

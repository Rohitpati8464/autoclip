"""Video processing pipeline stages."""

from __future__ import annotations

__all__ = ["STAGES", "Stage"]

from enum import StrEnum


class Stage(StrEnum):
    """Ordered pipeline stages.

    Stage order matters: a job that fails at ``REFRAME`` resumes from
    ``REFRAME``, reusing the artifacts every earlier stage left in
    ``work/{job_id}/``.
    """

    PREPARE = "prepare"
    TRANSCRIBE = "transcribe"
    HIGHLIGHTS = "highlights"
    REFRAME = "reframe"
    CAPTIONS = "captions"
    EXPORT = "export"

    @property
    def label(self) -> str:
        return {
            Stage.PREPARE: "Preparing media",
            Stage.TRANSCRIBE: "Transcribing",
            Stage.HIGHLIGHTS: "Finding highlights",
            Stage.REFRAME: "Reframing to vertical",
            Stage.CAPTIONS: "Generating captions",
            Stage.EXPORT: "Exporting clips",
        }[self]


#: Canonical stage order.
STAGES: tuple[Stage, ...] = tuple(Stage)

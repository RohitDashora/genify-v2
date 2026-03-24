"""Library row lifecycle for completed_metadata.artifact_status."""

ARTIFACT_IN_PROGRESS = "in_progress"
ARTIFACT_COMPLETE = "complete"
ARTIFACT_FAILED = "failed"
ARTIFACT_MERGE_ERROR = "merge_error"

# Draft-like: deleted with session when still linked; not deleted if session_id NULL (detached)
DRAFT_ARTIFACT_STATUSES = frozenset(
    {ARTIFACT_IN_PROGRESS, ARTIFACT_FAILED, ARTIFACT_MERGE_ERROR},
)

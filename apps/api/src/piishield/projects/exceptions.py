"""Project domain errors."""

from __future__ import annotations

from piishield.core.errors import ConflictError, NotFoundError


class ProjectNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Project not found")


class DuplicateSlugError(ConflictError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"A project with the slug {slug} already exists", code="duplicate_slug")

from __future__ import annotations

from pydantic import BaseModel
import requests
from analysis.models.swe_bench import Instance
import unidiff

from analysis.utility import fs_cache


class Diff(BaseModel):
    """Represents a diff between two versions of a file."""

    before: str
    after: str


class Patch(BaseModel):
    """Represents a git patch."""

    patch: str
    files: dict[str, Diff]

    @staticmethod
    def from_github(repo: str, base_commit: str, patch: str) -> Patch:
        """Create a Patch object from a GitHub patch.

        Requires downloading the source code of the base commit from GitHub.

        Args:
            repo: GitHub repository in the format 'owner/repo'.
            base_commit: Base commit hash.
            patch: Patch in unified diff format.
        """
        files: dict[str, Diff] = {}

        for file_patch in unidiff.PatchSet.from_string(patch):
            source = _get_source_from_github(repo, base_commit, file_patch.path)
            files[file_patch.path] = Diff(
                before=source, after="".join(_apply_diff(source, file_patch))
            )

        return Patch(patch=patch, files=files)

    @staticmethod
    def from_instance(instance: Instance) -> Patch:
        """Create a Patch object from a SWE-Bench instance."""
        return Patch.from_github(instance.repo, instance.base_commit, instance.patch)


def _apply_diff(source: str, file_patch: unidiff.PatchedFile) -> str:
    """Apply a diff to a source file."""
    lines = source.splitlines(keepends=True)

    for hunk in file_patch:
        start = hunk.target_start - 1
        del lines[start : start + hunk.target_length]
        lines[start:start] = [
            line[1:] for line in hunk.target_lines() if line.value.startswith("+")
        ]

    return "".join(lines)


@fs_cache
def _get_source_from_github(repo: str, commit: str, path: str) -> str:
    """Get the source code of a file from GitHub."""
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    response = requests.get(url)
    response.raise_for_status()
    return response.text

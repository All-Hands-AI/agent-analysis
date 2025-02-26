from __future__ import annotations

from pydantic import BaseModel
import requests
from analysis.models.swe_bench import Instance
import unidiff


class Diff(BaseModel):
    """Represents a diff between two versions of a file."""

    before: str
    after: str


class Patch(BaseModel):
    """Represents a git patch."""

    patch: str
    files: dict[str, Diff]

    @staticmethod
    def from_str(patch: str) -> Patch:
        """Parse a git patch into a Patch object.
        
        This doesn't work particularly well for small or disjoint patches, since each diff is missing lots of context.
        """
        files = {}
        current_file = None
        current_before = []
        current_after = []

        try:
            lines = patch.split("\n")
            for line in lines:
                if line.startswith("diff --git"):
                    # Save previous file if exists
                    if current_file:
                        files[current_file] = Diff(
                            before="\n".join(current_before),
                            after="\n".join(current_after),
                        )
                    # Start new file
                    current_file = line.split()[-1].lstrip("b/")
                    current_before = []
                    current_after = []
                elif line.startswith("+++") or line.startswith("---"):
                    continue
                elif line.startswith("+"):
                    current_after.append(line[1:])
                elif line.startswith("-"):
                    current_before.append(line[1:])
                elif line.startswith(" "):
                    current_before.append(line[1:])
                    current_after.append(line[1:])

            # Save last file
            if current_file:
                files[current_file] = Diff(
                    before="\n".join(current_before), after="\n".join(current_after)
                )
        except Exception:
            pass

        return Patch(files=files)

    @staticmethod
    def from_instance(instance: Instance) -> Patch:
        """Parse a Patch from an Instance.
        
        Requires downloading the original file from GitHub.
        """
        files: dict[str, Diff] = {}

        for patch in unidiff.PatchSet.from_string(instance.patch):
            path = patch.path
            url = f"https://raw.githubusercontent.com/{instance.repo}/{instance.base_commit}/{path}"
            response = requests.get(url)
            response.raise_for_status()
            
            lines = response.text.splitlines(keepends=True)

            for hunk in patch:
                # Calculate hunk position
                start = hunk.target_start - 1

                # Remove lines
                del lines[start : start + hunk.target_length]

                # Insert new lines
                lines[start:start] = [
                    line[1:]
                    for line in hunk.target_lines()
                    if line.value.startswith("+")
                ]

            files[path] = Diff(before=response.text, after="".join(lines))

        return Patch(patch=instance.patch, files=files)


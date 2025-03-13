from __future__ import annotations

import ast
import requests
import warnings
from enum import Enum
from typing import Any

import unidiff
from pydantic import BaseModel

from analysis.models.swe_bench import Instance
from analysis.utility import fs_cache


class ScopeKind(str, Enum):
    """Denotes the kind of scope boundary."""

    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"


class Scope(BaseModel):
    """Scopes represent syntactic and semantic blocks of code.

    We don't consider _all_ traditional scope boundaries, and instead stick with
    scopes that represent common abstractions that aren't control-flow.
    """

    kind: ScopeKind
    """The kind of scope."""

    name: str
    """The name for the scope, e.g. the class/function."""

    def __hash__(self):
        return hash((self.kind, self.name))

    def __eq__(self, other: Any):
        if not isinstance(other, Scope):
            return False

        return self.kind == other.kind and self.name == other.name


class Location(BaseModel):
    """Represents a location in a source file."""

    scopes: list[Scope]
    """
    A stack of scopes representing the conceptual location. Should always
    start with a `ScopeKind.FILE` scope.
    """

    line: int
    """The line number in the source file."""

    def __hash__(self) -> int:
        return hash((tuple(self.scopes), self.line))

    def __eq__(self, other: Any):
        if not isinstance(other, Location):
            return False

        return self.scopes == other.scopes and self.line == other.line

    def most_recent_scope(self, kind: ScopeKind) -> str | None:
        """Get the identifier for the most recent scope of a specific kind."""
        for scope in reversed(self.scopes):
            if scope.kind == kind:
                return scope.name
        return None


class Diff(BaseModel):
    """Represents a diff between two versions of a file."""

    before: str
    after: str


class Patch(BaseModel):
    """Represents a git patch."""

    patch: str
    """The raw git patch."""

    source: dict[str, str]
    """The source code of the files before the patch."""

    missing_files: list[str] = []

    @property
    def diffs(self) -> dict[str, Diff]:
        """Compute the list of diffs from the original source by applying the patch."""
        diffs: dict[str, Diff] = {}

        for file_patch in unidiff.PatchSet.from_string(self.patch, errors="ignore"):
            source = self.source[file_patch.path]
            updated_source = _apply_file_patch(source, file_patch)
            diffs[file_patch.path] = Diff(before=source, after=updated_source)

        return diffs

    @property
    def locations(self) -> list[Location]:
        """Find the locations in the source files that were changed by the patch."""

        if not hasattr(self, "_locations"):
            locations: list[Location] = []

            for filename, changed_lines in _parse_git_diff(self.patch).items():
                if filename not in self.missing_files:
                    locations.extend(
                        _find_changed_locations(
                            self.source[filename], filename, changed_lines
                        )
                    )

            setattr(self, "_locations", locations)

        return getattr(self, "_locations")

    @staticmethod
    def from_github(
        repo: str, base_commit: str, patch: str, skip_missing_files: bool = True
    ) -> Patch:
        """Create a Patch object from a GitHub patch.

        Requires downloading the source code of the base commit from GitHub.

        Args:
            repo: GitHub repository in the format 'owner/repo'.
            base_commit: Base commit hash.
            patch: Patch in unified diff format.
            skip_missing_files: Skip files that are not found in the base commit.
        """
        files: dict[str, str] = {}
        missing_files = []
        for filename, _ in _parse_git_diff(patch).items():
            try:
                files[filename] = _get_source_from_github(repo, base_commit, filename)
            except requests.HTTPError as e:
                if skip_missing_files:
                    missing_files.append(filename)
                    continue
                raise e

        return Patch(patch=patch, source=files, missing_files=missing_files)

    @staticmethod
    def from_instance(instance: Instance) -> Patch:
        """Create a Patch object from a SWE-Bench instance."""
        return Patch.from_github(instance.repo, instance.base_commit, instance.patch)


def _apply_file_patch(source: str, file_patch: unidiff.PatchedFile) -> str:
    """Apply a file patch to a source file.

    Args:
        source: The original source code.
        file_patch: The patch to apply.

    Returns:
        The patched source code.
    """
    # Split the source into lines, preserving the line endings
    original_lines = source.splitlines(keepends=True)

    # Track how line positions shift as we apply hunks
    line_shift = 0

    # Sort hunks by source_start to apply them in order
    hunks = sorted(file_patch, key=lambda hunk: hunk.source_start)

    for hunk in hunks:
        # Adjust position based on previous shifts
        source_pos = hunk.source_start - 1 + line_shift
        source_end = source_pos + hunk.source_length

        # Get the new lines to add (both context and added lines)
        # We only exclude removed lines (lines that start with -)
        new_lines = [line.value for line in hunk.target_lines() if not line.is_removed]

        # Calculate the shift caused by this hunk
        hunk_shift = len(new_lines) - hunk.source_length
        line_shift += hunk_shift

        # Replace the old lines with the new ones
        original_lines[source_pos:source_end] = new_lines

    # Just concatenate the lines (they already include newlines)
    return "".join(original_lines)


@fs_cache()
def _get_source_from_github(repo: str, commit: str, path: str) -> str:
    """Get the source code of a file from GitHub."""
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def _find_changed_locations(
    source: str, filename: str, changed_lines: set[int]
) -> list[Location]:
    """Find the locations in a source file that were changed by a set of lines.

    Args:
        source: The original source code.
        filename: The name of the file being analyzed.
        changed_lines: A set of line numbers that were changed in the file.

    Returns:
        A list of Location objects representing the changes.
    """
    # Parse the source code into an AST
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=SyntaxWarning)
        tree = ast.parse(source)

    # Walk the AST and track scopes
    tracker = ScopeTracker(filename, changed_lines)
    tracker.visit(tree)

    # Return all unique locations
    return list(set(tracker.locations))


class ScopeTracker(ast.NodeVisitor):
    """Utility class to track scopes in an AST."""

    def __init__(self, filename: str, changed_lines: set[int]):
        """Initialize the scope tracker.

        Args:
            filename: The name of the file being tracked. Generates the top-most
                scope for the analysis.

            changed_lines: A set of line numbers that were changed in the file.
                When the tracker hits a node corresponding to one of these lines
                a location is generated.
        """
        self.changed_lines = changed_lines
        self.current_scopes: list[Scope] = [Scope(kind=ScopeKind.FILE, name=filename)]
        self.locations: list[Location] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.current_scopes.append(Scope(kind=ScopeKind.CLASS, name=node.name))
        self._check_node(node)
        # Visit all child nodes
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.current_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.current_scopes.append(Scope(kind=ScopeKind.FUNCTION, name=node.name))
        self._check_node(node)
        # Visit all child nodes
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.current_scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.current_scopes.append(Scope(kind=ScopeKind.FUNCTION, name=node.name))
        self._check_node(node)
        # Visit all child nodes
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.current_scopes.pop()

    def _check_node(self, node: ast.AST):
        """Check if this specific node (not its children) has any lines that were changed."""
        if hasattr(node, "lineno"):
            line_no = node.lineno
            # For this test case, we're only interested in the exact line that changed
            if line_no in self.changed_lines:
                self.locations.append(
                    Location(
                        scopes=self.current_scopes.copy(),
                        line=line_no,
                    )
                )

    def generic_visit(self, node: ast.AST):
        """Called for all nodes for which no specific visit method exists."""
        self._check_node(node)
        # Continue visiting child nodes
        super().generic_visit(node)


def _parse_git_diff(diff_str: str) -> dict[str, set[int]]:
    """Parse a git diff string and return a dictionary mapping file names to sets of changed line numbers.

    Args:
        diff_str (str): The git diff string to parse

    Returns:
        dict[str, set[int]]: A dictionary mapping file names to sets of line numbers that were changed
    """
    result = {}
    current_file = None
    lines = diff_str.splitlines()
    line_index = 0

    while line_index < len(lines):
        line = lines[line_index]

        # Check for file header
        if line.startswith("diff --git"):
            # Find the file name from the b/ path
            next_line_index = line_index + 1
            while next_line_index < len(lines):
                next_line = lines[next_line_index]
                if next_line.startswith("--- "):
                    next_line_index += 1
                    continue
                if next_line.startswith("+++ "):
                    file_path = next_line[6:]  # Skip the '+++ ' prefix
                    # Remove a/ or b/ prefix if present
                    if file_path.startswith("b/"):
                        file_path = file_path[2:]
                    current_file = file_path
                    result[current_file] = set()
                    break
                next_line_index += 1
            line_index = next_line_index + 1
            continue

        # Check for hunk header
        if line.startswith("@@"):
            # Extract line numbers from hunk header
            # Format: @@ -<start>,<count> +<start>,<count> @@
            parts = line.split(" ")
            old_line_info = parts[1][1:]  # Remove the '-' prefix
            if "," in old_line_info:
                old_start = int(old_line_info.split(",")[0])
            else:
                old_start = int(old_line_info)

            # Move past hunk header
            line_index += 1

            # Process the hunk content
            current_line = old_start
            line_index_within_hunk = line_index

            # First pass: identify pairs of removed/added lines (changes)
            while line_index_within_hunk < len(lines) and not (
                lines[line_index_within_hunk].startswith("@@")
                or lines[line_index_within_hunk].startswith("diff --git")
            ):
                if (
                    line_index_within_hunk + 1 < len(lines)
                    and lines[line_index_within_hunk].startswith("-")
                    and lines[line_index_within_hunk + 1].startswith("+")
                ):
                    # Mark this as a change (will be processed in the next pass)
                    lines[line_index_within_hunk] = (
                        "!-" + lines[line_index_within_hunk][1:]
                    )
                    lines[line_index_within_hunk + 1] = (
                        "!+" + lines[line_index_within_hunk + 1][1:]
                    )
                line_index_within_hunk += 1

            # Second pass: process all lines
            while line_index < len(lines) and not (
                lines[line_index].startswith("@@")
                or lines[line_index].startswith("diff --git")
            ):
                line = lines[line_index]

                if line.startswith(" "):
                    # Unchanged line
                    current_line += 1
                elif line.startswith("!-"):
                    # Part of a change (remove+add) - add the line number
                    result[current_file].add(current_line)
                    current_line += 1
                elif line.startswith("!+"):
                    # Part of a change (remove+add) - already counted, just move on
                    pass
                elif line.startswith("-"):
                    # Pure removed line (not part of a change)
                    result[current_file].add(current_line)
                    current_line += 1
                elif line.startswith("+"):
                    # Pure added line (not part of a change)
                    result[current_file].add(current_line)
                    # Don't increment current_line for added lines

                line_index += 1

            # If we've reached the end of a hunk but not the start of a new one or file,
            # we need to continue to the next line
            if line_index < len(lines) and not (
                lines[line_index].startswith("@@")
                or lines[line_index].startswith("diff --git")
            ):
                line_index += 1

            continue

        line_index += 1

    return result

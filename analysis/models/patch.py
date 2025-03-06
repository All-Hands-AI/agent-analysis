from __future__ import annotations

import ast
import requests
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
    files: dict[str, Diff]

    @property
    def locations(self) -> list[Location]:
        """Find the locations in the source files that were changed by the patch."""

        if not hasattr(self, "_locations"):
            locations: list[Location] = []

            for path, diff in self.files.items():
                for file_patch in unidiff.PatchSet.from_string(self.patch):
                    if file_patch.path == path:
                        locations.extend(
                            _find_changed_locations(diff.before, file_patch)
                        )

            setattr(self, "_locations", locations)

        return getattr(self, "_locations")

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

        for file_patch in unidiff.PatchSet.from_string(patch, errors="ignore"):
            try:
                source = _get_source_from_github(repo, base_commit, file_patch.path)
                updated_source = _apply_file_patch(source, file_patch)
                files[file_patch.path] = Diff(before=source, after=updated_source)
            except requests.HTTPError:
                continue

        return Patch(patch=patch, files=files)

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
    source: str, file_patch: unidiff.PatchedFile
) -> list[Location]:
    """Find the locations in a source file that were changed by a patch.

    Args:
        source: The original source code.
        file_patch: The patch to apply.

    Returns:
        A list of Location objects representing the changes.
    """
    # Parse the source code into an AST
    tree = ast.parse(source)

    # Get all changed line numbers from the patch
    changed_lines = set()
    for hunk in file_patch:
        for line in hunk:
            if line.is_added or line.is_removed:
                changed_lines.add(line.target_line_no)

    # Walk the AST and track scopes
    tracker = ScopeTracker(file_patch.path, changed_lines)
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

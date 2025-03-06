from __future__ import annotations

import ast
import requests
import re
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

            for path, diff in self.diffs.items():
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
        files: dict[str, str] = {}
        for filename, _ in _parse_git_diff(patch).items():
            files[filename] = _get_source_from_github(repo, base_commit, filename)

        return Patch(patch=patch, source=files)

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

def _parse_git_diff(diff_str):
    """
    Parse a git diff string and return a dictionary mapping filenames to sets of line numbers
    from the original source that were modified (including lines where content was added).
    
    Args:
        diff_str: String representation of a git diff
        
    Returns:
        dict[str, set[int]]: Mapping of filenames to sets of modified line numbers
    """
    result = {}
    current_file = None
    in_hunk = False
    hunk_modified_lines = set()
    
    # Parse the diff line by line
    lines = diff_str.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # File headers
        if line.startswith('--- '):
            # End any current hunk processing
            if in_hunk and current_file:
                # Add any leftover modifications from previous hunk
                result[current_file].update(hunk_modified_lines)
                hunk_modified_lines = set()
                in_hunk = False
            
            # Only process non-null files
            if not line.startswith('--- /dev/null'):
                current_file = line[4:].strip()
                if current_file.startswith('a/'):
                    current_file = current_file[2:]
                result[current_file] = set()
            else:
                # This is a new file being added, will get name from +++ line
                current_file = None
        
        elif line.startswith('+++ '):
            # End any current hunk processing
            if in_hunk and current_file:
                # Add any leftover modifications from previous hunk
                result[current_file].update(hunk_modified_lines)
                hunk_modified_lines = set()
                in_hunk = False
            
            if line.startswith('+++ /dev/null'):
                # This is a file being deleted
                pass
            elif current_file is None:
                # If we're dealing with a new file (previous line was "--- /dev/null")
                # or if we somehow missed the "---" line
                new_file = line[4:].strip()
                if new_file.startswith('b/'):
                    new_file = new_file[2:]
                current_file = new_file
                result[current_file] = set()
        
        # Hunk headers
        elif line.startswith('@@') and current_file:
            # End any current hunk processing
            if in_hunk:
                # Add any leftover modifications from previous hunk
                result[current_file].update(hunk_modified_lines)
                hunk_modified_lines = set()
            
            # Start new hunk processing
            in_hunk = True
            match = re.search(r'-(\d+)(?:,(\d+))?', line)
            if match:
                start_line = int(match.group(1))
                current_line = start_line
                
                # Special case for new files - they start at position 0
                if start_line == 0:
                    hunk_modified_lines.add(0)
            else:
                # Malformed hunk header, skip it
                in_hunk = False
                i += 1
                continue
        
        # Lines in a hunk
        elif in_hunk and current_file:
            if line.startswith('-'):
                # Line was removed from the original file
                hunk_modified_lines.add(current_line)
                current_line += 1
            elif line.startswith('+'):
                # Line was added - mark the insertion point
                # The insertion point is the current position in the original file
                hunk_modified_lines.add(current_line)
                # Don't increment the line counter for additions
            elif not line.startswith('\\'):  # Ignore "\ No newline at end of file"
                # Unchanged context line
                current_line += 1
        
        i += 1
    
    # Add any modifications from the last hunk
    if in_hunk and current_file and hunk_modified_lines:
        result[current_file].update(hunk_modified_lines)
    
    # Post-process for deleted files to ensure all lines are marked
    for file in list(result.keys()):
        file_content = "\n".join(lines)
        if f"--- a/{file}" in file_content and "+++ /dev/null" in file_content:
            # This file was deleted - try to find how many lines were deleted
            match = re.search(r'@@ -1,(\d+) \+0,0 @@', file_content)
            if match:
                line_count = int(match.group(1))
                # Mark all lines as modified
                result[file] = set(range(1, line_count + 1))
    
    return result

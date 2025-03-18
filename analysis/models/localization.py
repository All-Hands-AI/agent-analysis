from pydantic import BaseModel
from enum import Enum
from typing import Any

import ast
import warnings


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


def find_changed_locations(
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


class SystemLocations(BaseModel):
    system: str
    locations: dict[str, list[Location]]


class LocalizationReport(BaseModel):
    systems: list[SystemLocations]

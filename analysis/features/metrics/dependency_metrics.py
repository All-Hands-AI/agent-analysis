from __future__ import annotations

import ast
import networkx as nx # type: ignore

from analysis.features.metrics.metrics import Metrics
from analysis.features.metrics.utility import parse_code_fragment

class DependencyMetrics(Metrics):
    number_of_function_calls: int = 0
    number_of_unique_calls: int = 0
    max_call_depth: int = 0
    number_of_circular_dependencices: int = 0
    import_depth: int = 0
    number_of_internal_dependencies: int = 0
    number_of_external_dependencies: int = 0
    
    def add_call_graph(self, call_graph: nx.DiGraph) -> None:
        """Add call graph to metrics.
        
        The call graph is needed to determine the number of unique calls, the maximum call depth, and the number of circular dependencies
        """
        self.number_of_unique_calls = len(call_graph.nodes())
        if self.number_of_unique_calls == 0:
            self.max_call_depth = 0
        else:
            self.max_call_depth = max(
                len(nx.shortest_path(call_graph, source=source, target=target))
                for source in call_graph.nodes()
                for target in call_graph.nodes()
                if nx.has_path(call_graph, source, target)
            ) - 1
        try:
            self.number_of_circular_dependencices = len(list(nx.simple_cycles(call_graph)))
        except nx.NetworkXNoCycle:
            self.number_of_circular_dependencices = 0

class DependencyMetricsVisitor(ast.NodeVisitor):
    """AST visitor for extracting dependency relations from the code."""
    
    def __init__(self):
        self.dependency_metrics = DependencyMetrics()
        self.function_calls = set()
        self.call_graph = nx.DiGraph()
        self.current_function = None
        
    def visit_Call(self, node):
        """Visit function calls."""
        self.dependency_metrics.number_of_function_calls += 1
        
        # Get function name
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        else:
            func_name = "unknown"
        
        self.function_calls.add(func_name)
        
        # Add to call graph
        if self.current_function and func_name != "unknown":
            self.call_graph.add_edge(self.current_function, func_name)
        
        self.generic_visit(node)

def extract_dependency_metrics(code: str) -> DependencyMetrics:
    """Extract advanced features from Python code."""
    try:
        tree = parse_code_fragment(code)
    except (SyntaxError, ValueError):
        return DependencyMetrics()
    
    visitor = DependencyMetricsVisitor()
    visitor.visit(tree)
    visitor.dependency_metrics.add_call_graph(visitor.call_graph)

    return visitor.dependency_metrics

DependencyMetrics.from_str = extract_dependency_metrics
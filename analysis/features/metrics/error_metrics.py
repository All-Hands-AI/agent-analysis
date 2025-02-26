from __future__ import annotations

import ast

from analysis.features.metrics.metrics import Metrics
from analysis.features.metrics.utility import parse_code_fragment

class ErrorMetrics(Metrics):
    number_of_try_blocks: int = 0
    number_of_except_handlers: int = 0
    number_of_finally_blocks: int = 0
    number_of_raise_statements: int = 0
    max_except_depth: int = 0
    number_of_broad_excepts: int = 0  # except: or except Exception:
    number_of_specific_excepts: int = 0  # except SpecificError:


class ErrorMetricsVisitor(ast.NodeVisitor):
    """AST visitor for extracting advanced code features."""
    
    def __init__(self):
        self.error_metrics = ErrorMetrics()
        self.current_except_depth = 0

    def visit_Try(self, node):
        """Visit try blocks."""
        self.error_metrics.number_of_try_blocks += 1
        self.current_except_depth += 1
        self.error_metrics.max_except_depth = max(
            self.error_metrics.max_except_depth,
            self.current_except_depth
        )
        
        # Analyze except handlers
        for handler in node.handlers:
            self.error_metrics.number_of_except_handlers += 1
            if handler.type is None or (
                hasattr(handler.type, 'id') and 
                handler.type.id == 'Exception'
            ):
                self.error_metrics.number_of_broad_excepts += 1
            else:
                self.error_metrics.number_of_specific_excepts += 1
        
        if node.finalbody:
            self.error_metrics.number_of_finally_blocks += 1
        
        self.generic_visit(node)
        self.current_except_depth -= 1
    
    def visit_Raise(self, node):
        """Visit raise statements."""
        self.error_metrics.number_of_raise_statements += 1
        self.generic_visit(node)


def extract_error_metrics(code: str) -> ErrorMetrics:
    """Extract advanced features from Python code."""
    try:
        tree = parse_code_fragment(code)
    except (SyntaxError, ValueError):
        return ErrorMetrics()
    
    visitor = ErrorMetricsVisitor()
    visitor.visit(tree)

    return visitor.error_metrics

ErrorMetrics.from_str = extract_error_metrics
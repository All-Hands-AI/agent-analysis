import ast
import textwrap

def normalize_indentation(code: str) -> str:
    """Remove any common leading indentation from every line in code."""
    if not code:
        return code
    
    # Filter out empty lines for dedent calculation
    lines = [line for line in code.splitlines() if line.strip()]
    if not lines:
        return code
    
    # Dedent the code
    return textwrap.dedent(code)

def parse_code_fragment(code: str) -> ast.AST:
    """Try parsing code with various indentation fixes."""
    # List of transformations to try
    attempts = [
        lambda x: x,  # Try as-is
        normalize_indentation,  # Try with normalized indentation
        lambda x: "if True:\n" + textwrap.indent(x, '    '),  # Try wrapping in if block
        lambda x: "def dummy():\n" + textwrap.indent(x, '    ')  # Try wrapping in function
    ]
    
    for transform in attempts:
        try:
            transformed_code = transform(code)
            return ast.parse(transformed_code)
        except (SyntaxError, IndentationError):
            continue
    
    # If full parsing fails, try line by line
    valid_nodes = []
    lines = code.splitlines()
    
    for line in lines:
        line = line.strip()  # Remove all indentation
        if not line:
            continue
            
        try:
            tree = ast.parse(line)
            if isinstance(tree, ast.Module) and tree.body:
                valid_nodes.extend(tree.body)
        except (SyntaxError, IndentationError):
            continue
    
    if valid_nodes:
        return ast.Module(body=valid_nodes, type_ignores=[])
    
    print("Failed to parse code fragment")
    raise ValueError()
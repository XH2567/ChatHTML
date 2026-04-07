import ast
import astor
import os

with open("app.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

def filter_nodes(names):
    new_body = []
    # Keep all imports
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            new_body.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in names:
                new_body.append(node)
        elif isinstance(node, ast.Assign) and names is not None:
            # simple assigns
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    new_body.append(node)
                    break
        elif names is None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign)):
            # Fallback for others
            new_body.append(node)
            
    m = ast.Module(body=new_body, type_ignores=[])
    return astor.to_source(m)

# Actually astor strips comments and reformats. Is that OK? Yes, if it is functional.
print("AST test check")

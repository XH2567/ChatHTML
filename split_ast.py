import ast
import collections

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
    
with open("app.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

nodes_info = {}

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        name = node.name
        start = node.lineno
        end = getattr(node, 'end_lineno', start)
        nodes_info[name] = (start, end)
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                nodes_info[t.id] = (node.lineno, getattr(node, 'end_lineno', node.lineno))

print(nodes_info.keys())

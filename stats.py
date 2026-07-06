import ast, os, sys
from collections import defaultdict

root = 'tools'
total_files = 0
modules = {}

for dirpath, dirs, files in os.walk(root):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(dirpath, f)
        try:
            tree = ast.parse(open(path, encoding='utf-8').read(), filename=path)
        except Exception as e:
            print(f"SKIP {path}: {e}")
            continue
        loc = len(tree.body)
        imp = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        cls = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        fnc = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        total_files += 1
        key = path.replace(os.sep, '/')
        modules[key] = {'loc': loc, 'imports': imp, 'classes': cls, 'funcs': fnc}

print('=== Module Stats ===')
print(f'{"File":45s} {"LOC":>4s} {"Import":>6s} {"Cls":>3s} {"Fn":>3s}')
print('-'*65)
for k in sorted(modules):
    m = modules[k]
    print(f'{k:45s} {m["loc"]:4d} {m["imports"]:6d} {m["classes"]:3d} {m["funcs"]:3d}')
print(f'\nTotal .py files: {total_files}')

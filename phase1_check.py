import ast, pathlib
ROOT=pathlib.Path(__file__).parent
files=list(ROOT.rglob("*.py"))
for p in files:
    ast.parse(p.read_text(encoding="utf-8"))
print(f"OK: syntax checked {len(files)} Python files")

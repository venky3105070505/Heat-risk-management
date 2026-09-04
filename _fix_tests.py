"""Fix all COUNT query aliases in test_app.py"""
with open("test_app.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'SELECT COUNT(*) c FROM communications',
    'SELECT COUNT(*) FROM communications'
)
content = content.replace('.fetchone()["c"]', '.fetchone()[0]')

with open("test_app.py", "w", encoding="utf-8") as f:
    f.write(content)

import ast
ast.parse(content)
print("Fixed and syntax OK,", len(content.splitlines()), "lines")

import re
with open('/home/xings/LatexML/webapp/views.py', 'r') as f:
    content = f.read()

script = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
if script:
    print(script.group(1)[:100])

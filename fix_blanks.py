import sys
path = 'c:/Users/SINAN/padikkunnundo.app/templates/base.html'
with open(path, 'r', newline='') as f:
    content = f.read()
old = '</style>\n\n\n\n\n  {% block head %}'
new = '</style>\n\n  {% block head %}'
if old in content:
    content = content.replace(old, new)
    with open(path, 'w', newline='') as f:
        f.write(content)
    print('Fixed')
else:
    print('Pattern not found')
    idx = content.find('</style>')
    print(repr(content[idx:idx+60]))

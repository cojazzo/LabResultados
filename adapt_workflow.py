import json
import sys

file_path = 'LAB-01 Recepción Cuestionario.json'
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print('Error reading file:', e)
    sys.exit(1)

for node in data.get('nodes', []):
    if node.get('type') == 'n8n-nodes-base.httpRequest':
        old_url = node['parameters'].get('url', '')
        if 'http://host.docker.internal:8000' in old_url:
            node['parameters']['url'] = old_url.replace('http://host.docker.internal:8000', 'http://backend:8000')

out_path = 'LAB-01 Recepción Cuestionario Server.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Success')

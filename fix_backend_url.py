import urllib.request
import json

api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZjY2MTU5MC03ZDdjLTQ1ODMtOWZjNy1hOTdmZWI2NWI3ZTEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNGI4YmE3MzMtNTVlYS00Y2FlLTk0NWYtZTllMDJiYjcwYzQ5IiwiaWF0IjoxNzg0MzE3MDUxLCJleHAiOjE3OTIwMzY4MDB9.HligG488CDsdPAd0uIS_TSCi0KAAVfcelyFwv_rXSHc'
base_url = 'http://100.125.127.8:5678/api/v1'

url_wf = f'{base_url}/workflows/RAe54lQ1cetHZzyB'

req_get = urllib.request.Request(url_wf, headers={'X-N8N-API-KEY': api_key})
try:
    with urllib.request.urlopen(req_get) as response:
        data = json.loads(response.read().decode())
except Exception as e:
    print('Error fetching:', e)
    exit(1)

for node in data.get('nodes', []):
    if node.get('type') == 'n8n-nodes-base.httpRequest':
        old_url = node['parameters'].get('url', '')
        if 'http://host.docker.internal:8000' in old_url:
            node['parameters']['url'] = old_url.replace('http://host.docker.internal:8000', 'http://100.125.127.8:8000')

payload = {
    "name": data.get("name"),
    "nodes": data.get("nodes"),
    "connections": data.get("connections"),
    "settings": {"executionOrder": "v1"}
}

req_put = urllib.request.Request(url_wf, data=json.dumps(payload).encode('utf-8'), headers={'X-N8N-API-KEY': api_key, 'Content-Type': 'application/json'}, method='PUT')
try:
    with urllib.request.urlopen(req_put) as response:
        print('Updated workflow backend URL to 100.125.127.8:8000')
except urllib.error.HTTPError as e:
    print('Error updating workflow:', e.code, e.read().decode())

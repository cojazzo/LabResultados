# -*- coding: utf-8 -*-
import urllib.request
import json

api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZjY2MTU5MC03ZDdjLTQ1ODMtOWZjNy1hOTdmZWI2NWI3ZTEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNGI4YmE3MzMtNTVlYS00Y2FlLTk0NWYtZTllMDJiYjcwYzQ5IiwiaWF0IjoxNzg0MzE3MDUxLCJleHAiOjE3OTIwMzY4MDB9.HligG488CDsdPAd0uIS_TSCi0KAAVfcelyFwv_rXSHc'
url = 'http://100.125.127.8:5678/api/v1/workflows/RAe54lQ1cetHZzyB'

with open('workflow_RAe54lQ1cetHZzyB.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for node in data.get('nodes', []):
    if node.get('id') == '3e7a82d8-6f70-4ccd-a958-1f62ab808c57':
        node['type'] = 'n8n-nodes-base.readWriteFile'
        node['parameters'] = {
            'operation': 'delete',
            'fileName': "=/data/cola_envio/resultados/{{ $json.id }}.{{ $json.estado === 'enviado' ? 'ok' : 'err' }}.json"
        }

payload = {
    "name": "LabResultados - Envio de resultados",
    "nodes": data.get("nodes"),
    "connections": data.get("connections"),
    "settings": {"executionOrder": "v1"}
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'X-N8N-API-KEY': api_key, 'Content-Type': 'application/json'}, method='PUT')
try:
    with urllib.request.urlopen(req) as response:
        print('Success!')
except urllib.error.HTTPError as e:
    print('Error:', e.code, e.read().decode())

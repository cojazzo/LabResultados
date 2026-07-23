import urllib.request
import json

url = 'http://100.125.127.8:5678/api/v1/workflows'
req = urllib.request.Request(url, headers={'X-N8N-API-KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZjY2MTU5MC03ZDdjLTQ1ODMtOWZjNy1hOTdmZWI2NWI3ZTEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNGI4YmE3MzMtNTVlYS00Y2FlLTk0NWYtZTllMDJiYjcwYzQ5IiwiaWF0IjoxNzg0MzE3MDUxLCJleHAiOjE3OTIwMzY4MDB9.HligG488CDsdPAd0uIS_TSCi0KAAVfcelyFwv_rXSHc'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for wf in data.get('data', []):
            print(f"ID: {wf.get('id')} | Name: {wf.get('name')} | Active: {wf.get('active')}")
except Exception as e:
    print('Error:', e)

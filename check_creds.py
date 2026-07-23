# -*- coding: utf-8 -*-
import urllib.request
import json

api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZjY2MTU5MC03ZDdjLTQ1ODMtOWZjNy1hOTdmZWI2NWI3ZTEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNGI4YmE3MzMtNTVlYS00Y2FlLTk0NWYtZTllMDJiYjcwYzQ5IiwiaWF0IjoxNzg0MzE3MDUxLCJleHAiOjE3OTIwMzY4MDB9.HligG488CDsdPAd0uIS_TSCi0KAAVfcelyFwv_rXSHc'
url = 'http://100.125.127.8:5678/api/v1/credentials/z09sgHXpGFFcOguW'

req = urllib.request.Request(url, headers={'X-N8N-API-KEY': api_key})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print('Error:', e)

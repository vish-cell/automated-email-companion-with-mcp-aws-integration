import requests, json
p = {"keywords":["aws","email","serverless"], "attachments": []}
try:
    resp = requests.post('http://127.0.0.1:6278/tools/summarize_context', json=p, timeout=10)
    print('STATUS', resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)
except Exception as e:
    print('POST error:', e)

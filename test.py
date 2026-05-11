import requests

url = "http://10.199.194.160:22235/api"

text = "村名生活变了样。"

session = requests.Session()
session.trust_env = False  # 关键：不使用系统代理

r = session.post(
    url,
    json={"content": text},
    headers={"Content-Type": "application/json"},
    timeout=30
)

print("状态码:", r.status_code)
print("原始返回:", r.text)

data = r.json()
print("校对结果:", data.get("correct"))
print("修改建议:", data.get("result"))
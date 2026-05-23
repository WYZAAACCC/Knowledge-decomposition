import sys
sys.path.insert(0, '../src')
from src.deepseek_client import get_deepseek_client

client = get_deepseek_client()
try:
    result = client.chat_json(
        messages=[{"role": "user", "content": "请用JSON格式回答: {\"name\": \"test\"}"}],
        temperature=0.0,
        use_reasoner=False
    )
    print("Success:", type(result), result)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

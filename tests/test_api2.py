import sys
import os
import dotenv

dotenv.load_dotenv()

api_key = os.environ.get("DEEPSEEK_API_KEY", "")
print(f"API Key exists: {bool(api_key)}")
print(f"API Key length: {len(api_key)}")
print(f"API Key prefix: {api_key[:8]}..." if api_key else "No API key")

sys.path.insert(0, '../src')
from src.deepseek_client import DeepSeekClient

try:
    client = DeepSeekClient.from_env()
    print("Client created successfully")

    result = client.chat_json(
        messages=[{"role": "user", "content": "Hello, respond with JSON: {\"status\": \"ok\"}"}],
        temperature=0.0,
        use_reasoner=False
    )
    print(f"API call success: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

import os
from utils import get_next_api_key, call_llm_with_rotation

# Mock environment
os.environ["GEMINI_API_KEYS"] = "key1,key2,key3"

print("Rotation test:")
for i in range(5):
    key, idx = get_next_api_key()
    print(f"Call {i}: index={idx}, key={key}")

print("\nCall LLM fallback test:")
# This should fail because keys are fake, and use the fallback
result = call_llm_with_rotation("This is sentence one. This is sentence two. This is sentence three. This should be truncated.")
print("Fallback Result:", result)

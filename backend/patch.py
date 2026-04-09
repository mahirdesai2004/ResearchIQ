import os
import re

file_path = "/Users/mahir/ResearchIQ/backend/llm_layer.py"
with open(file_path, "r") as f:
    content = f.read()

header_replacement = """# Persistent cache to save API calls
import json

CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "llm_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        pass

_LLM_CACHE = load_cache()
"""

# Replace the old cache initialization
content = content.replace("# Simple in-memory cache to save API calls\n_LLM_CACHE = {}\n", header_replacement)

# Replace the assignments. Regex matches indentation and assignment
# Ex: "    _LLM_CACHE[cache_key] = ans" -> "    _LLM_CACHE[cache_key] = ans\n    save_cache(_LLM_CACHE)"
content = re.sub(r'^([ \t]*)(_LLM_CACHE\[cache_key\] = [^\n]+)$', r'\1\2\n\1save_cache(_LLM_CACHE)', content, flags=re.MULTILINE)

with open(file_path, "w") as f:
    f.write(content)

print("llm_layer.py patched successfully.")

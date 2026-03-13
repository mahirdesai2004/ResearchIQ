import os
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ResearchIQ")

api_keys_str = os.getenv("GEMINI_API_KEYS", "")
API_KEYS = [k.strip() for k in api_keys_str.split(",") if k.strip()]
_current_key_idx = 0

def call_llm_with_rotation(prompt: str) -> str:
    global _current_key_idx
    if not API_KEYS:
        return "Summary not available."
        
    for _ in range(len(API_KEYS)):
        current_key = API_KEYS[_current_key_idx]
        _current_key_idx = (_current_key_idx + 1) % len(API_KEYS)
        
        try:
            client = genai.Client(api_key=current_key)
            # using gemini-2.5-flash as default
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            logger.warning(f"LLM failed with a key: {e}")
            continue
            
    return "Summary not available."

def summarize_abstract(abstract: str) -> str:
    if not API_KEYS:
        # Fallback to first 3 sentences
        sentences = abstract.split('.')
        return '.'.join(sentences[:3]).strip() + "." if sentences else abstract
        
    prompt = (
        "You are an AI Research Assistant. Analyze the following scientific abstract and provide a structured, "
        "concise summary (max 3 sentences). Focus on: \n"
        "1. The primary problem addressed.\n"
        "2. The core technical contribution.\n"
        "3. The significance of the results.\n\n"
        f"Abstract: {abstract}\n\n"
        "Format: Return only the analysis text, starting with 'AI Analysis:'"
    )
    return call_llm_with_rotation(prompt)

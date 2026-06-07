import os
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    return {
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "gemini_model_name": os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash"),
    }
"""Quick diagnostic: test multiple Gemini models with a real image."""
import os
import sys
from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai
from google.genai import types

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: No GEMINI_API_KEY found in .env"); sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Candidate models to test (vision-capable from list)
CANDIDATES = [
    "gemini-3.5-flash",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
]

IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
if not IMAGE_PATH:
    print("Usage: python test_models.py /path/to/image.jpg"); sys.exit(1)

with open(IMAGE_PATH, "rb") as f:
    img_bytes = f.read()

print(f"\nTesting {len(CANDIDATES)} models with image: {IMAGE_PATH}\n{'='*60}")

for model_name in CANDIDATES:
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                "Does this image show a damaged vehicle? Reply with just yes or no."
            ],
        )
        print(f"[OK]   {model_name}: '{response.text.strip()}'")
    except Exception as e:
        print(f"[FAIL] {model_name}: {str(e)[:120]}")

print("="*60)

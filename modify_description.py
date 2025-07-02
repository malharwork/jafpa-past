import json
import time
import requests
from config import GEMINI_API_KEY

# === Constants ===
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
HEADERS = {
    "Content-Type": "application/json"
}

# --- Prompts ---
DESC_PROMPT_TEMPLATE = (
    "You are a product description assistant. Rewrite a product description for the product in 50 words only. "
    "Base it on the title provided. Ensure the description is detailed, informative,to the point and easy to understand. "
    "Include qualities of the product, its cut, typical use cases, nutritional benefits, and what sets it apart. "
    "Do NOT include recipes or instructions. Just provide a high-quality informative product description hich is NOT marketing tone.\n\n"
    "Product Title: {title}"
)

TYPE_PROMPT_TEMPLATE = (
    "Given the following product title and description and category, classify its type strictly as one of the following: "
    "'chicken', 'mutton', 'seafood', 'eggs', or 'ready to cook'. Respond with ONLY the type word, nothing else.\n\n"
    "Title: {title}\n"
    "Description: {description}\n" 
    "Category: {category}"
)

# --- Gemini Helper ---
def call_gemini(prompt: str) -> str:
    body = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    while True:
        response = requests.post(API_URL, headers=HEADERS, json=body)

        if response.status_code == 200:
            try:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (KeyError, IndexError):
                return "ERROR"

        elif response.status_code == 429:
            print("⚠️ Rate limit hit. Handling backoff...")
            try:
                retry_info = response.json()["error"]["details"]
                retry_delay = 30  # default fallback
                for detail in retry_info:
                    if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                        retry = detail.get("retryDelay", "30s")
                        retry_delay = int(retry.replace("s", "").strip())
                print(f"🔁 Waiting for {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                continue  # retry the request
            except Exception:
                print("Fallback wait: 30s")
                time.sleep(30)
                continue

        else:
            print(f"❌ Gemini API error {response.status_code}: {response.text}")
            return "ERROR"


# --- File Processor ---
def process_file(filepath: str):
    print(f"Processing: {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
        data = json.load(file)

    for i, product in enumerate(data):
        title = product.get("title", "")
        category=product.get("category","")
        if not title:
            continue

        print(f"{i+1}. Generating description for: {title}")
        new_desc = call_gemini(DESC_PROMPT_TEMPLATE.format(title=title))
        product["description"] = new_desc
        time.sleep(0.5)

        print(f"{i+1}. Predicting type for: {title}")
        predicted_type = call_gemini(TYPE_PROMPT_TEMPLATE.format(title=title, description=new_desc,category=category)).lower()
        # fallback to chicken if unexpected
        if predicted_type not in ["chicken", "mutton", "seafood", "eggs", "ready to cook"]:
            predicted_type = "chicken"
        product["type"] = predicted_type
        time.sleep(0.5)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    print(f"✅ Finished updating: {filepath}")

# --- Main ---
if __name__ == "__main__":
    process_file("japfa_pune_2025_04_14_17_49_23.json")
    process_file("licious_pune_2025_04_14_17_09_46.json")

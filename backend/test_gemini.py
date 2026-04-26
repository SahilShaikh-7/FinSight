import google.generativeai as genai

api_key = 'AIzaSyDQbgNm70ac8sfNPju8ZkuSlJso0-i-n98'
genai.configure(api_key=api_key)

print("Testing Gemini API models...\n")
models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']

for model_name in models_to_try:
    try:
        print(f"Trying {model_name}...", end=" ", flush=True)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content('Hello')
        print(f"✅ SUCCESS\nResponse: {response.text[:100]}")
        break
    except Exception as e:
        print(f"❌ {type(e).__name__}: {str(e)[:80]}")

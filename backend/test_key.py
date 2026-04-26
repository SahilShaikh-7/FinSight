import google.generativeai as genai
genai.configure(api_key="AIzaSyAfhX3JzJSzomNOGLhgHP5_AmaRllxWIwQ")
models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
for model_name in models:
    try:
        m = genai.GenerativeModel(model_name)
        r = m.generate_content("Hi")
        print(f"✅ {model_name}: Success")
        break
    except Exception as e:
        print(f"❌ {model_name}: {str(e)[:80]}")


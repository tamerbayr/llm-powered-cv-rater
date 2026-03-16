import requests
import os
import re
import json
import hashlib
from time import sleep

def clear_job_cache(job_text):
    """iş ilanının bellekteki kaydını siler
    returns:
    True: silindi, False: bulunamadı"""
    job_hash = hashlib.sha256(job_text.strip().encode('utf-8')).hexdigest()
    cache_path = os.path.join("job_cache", f"{job_hash}.json")
    
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return True
    return False

def detect_provider(api_key):
    api_key = api_key.strip()
    
    if api_key.startswith("sk-ant-"):
        return {
            "provider": "Anthropic",
            "endpoint": "https://api.anthropic.com/v1/messages",
            "default_model": "claude-3-5-haiku-20241022"
        }
    elif api_key.startswith("sk-or-"):
        return {
            "provider": "OpenRouter",
            "endpoint": "https://openrouter.ai/api/v1/chat/completions",
            #"default_model": "meta-llama/llama-3.3-70b-instruct:free"
            "default_model": "stepfun/step-3.5-flash:free"
        }
    elif api_key.startswith("sk-proj-") or api_key.startswith("sk-"):
        return {
            "provider": "OpenAI",
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "default_model": "gpt-4o-mini"
        }
    elif api_key.startswith("AIza"):
        return {
            "provider": "Gemini",
            "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "default_model": "gemini-1.5-flash"
        }
    else:
        return None

def create_env():
    
    with open("secrets.txt", "w") as f:
        api_key = input("API Key: ")
        f.write(f"API_KEY={api_key}\n")

def get_env():
    try:
        with open("secrets.txt", "r") as f:
            for line in f:
                if line.startswith("API_KEY="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        print("secrets.txt dosyası bulunamadı, API key girin")
        create_env() 
        return get_env()

def post_chat(prompt: list, config=None, api_key=None):
    endpoint = config["endpoint"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "JOB_RATER",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["default_model"],
        "messages": prompt,
        "temperature": 0,
    }
    
    last_response = None
    for i in range(5):
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30,
        )
        last_response = response
        
        if response.status_code == 200:
            return response.json()
        
        print(f"LLM hata gönderdi ({response.status_code}). "
              f"Deneme {i+1}/5. 5 saniye içinde tekrar deneniyor...")
        sleep(5)
    
    print("STATUS:", last_response.status_code)
    print("RESPONSE:", last_response.text)
    last_response.raise_for_status()
    
class PromptBuilder:
    def __init__(self):
        self.data = self.load_prompts()
            
    def load_prompts(self):
        try:
            with open("prompts.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"HATA: prompts.json okunamadı: {e}")
            return None      
            
    def build(self, job_text):
        sections = re.split(r'\n(?=[A-Z][a-z\s]+:?\n)', job_text) 
        formatted_input = "\n---\n".join([f"SECTION {i}: {s.strip()}" for i, s in enumerate(sections)])
        
        data = self.load_prompts()
        if not data: return []
        
        messages = []
        messages.append(data["main_prompt"])
        messages.extend(data["few_shot_examples"])
        messages.append({
            "role": "user",
            "content": f"analyze this job posting and extract requirements:\n\n{formatted_input}"
        })
        
        return messages

def parse_llm_response(response):
    """
    llm'den gelen metni temizleyip json yapar 
    """
    try:
        content = response["choices"][0]["message"]["content"]
        print(f"\n-------------LLM CEVABI \n {content} \n-------------------------") #debug
        clean_json = re.sub(r'```json\s*|\s*```', '', content).strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"JSON hatası: {e}")
        return None   
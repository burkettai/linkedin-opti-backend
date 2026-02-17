import os
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import google.generativeai as genai

app = Flask(__name__)
CORS(app)  # Allow frontend to communicate with backend

# --- CONFIGURATION ---
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
# Use the "LinkedIn Profile Scraper" actor (e.g., curious_coder or similar)
# You need the Actor ID. Example: "kfiWxhKTewlkgjtyK" is a popular one.
APIFY_ACTOR_ID = "kfiWxhKTewlkgjtyK" 

GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

def scrape_linkedin(profile_url):
    """Triggers Apify actor and waits for result."""
    api_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs?token={APIFY_TOKEN}"
    
    # Input strictly typed for the specific actor you are using
    payload = {
        "urls": [{"url": profile_url}],
        "minDelay": 2,
        "maxDelay": 5,
        "proxy": {"useApifyProxy": True}
    }
    
    # 1. Start the Scrape
    response = requests.post(api_url, json=payload)
    if response.status_code != 201:
        return None
    
    run_id = response.json()['data']['id']
    
    # 2. Poll for completion (Simple polling for demo purposes)
    # In production, use webhooks for better performance
    while True:
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        status_res = requests.get(status_url).json()
        status = status_res['data']['status']
        
        if status == "SUCCEEDED":
            break
        elif status in ["FAILED", "ABORTED"]:
            return None
        time.sleep(3) # Wait 3 seconds before checking again

    # 3. Fetch Dataset
    dataset_id = status_res['data']['defaultDatasetId']
    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    data_res = requests.get(data_url)
    
    # Return the first profile found
    return data_res.json()[0] if data_res.json() else None

@app.route('/optimize', methods=['POST'])
def optimize_profile():
    data = request.json
    profile_url = data.get('url')
    target_job = data.get('job')

    if not profile_url or not target_job:
        return jsonify({"error": "Missing URL or Job"}), 400

    # 1. Scrape
    scraped_data = scrape_linkedin(profile_url)
    if not scraped_data:
        return jsonify({"error": "Could not access profile. Ensure it is public."}), 500

    # 2. Optimize with Gemini 3 Flash
    # We construct a lean prompt to save tokens and ensure focus
    prompt = f"""
    You are an expert Career Coach and LinkedIn Copywriter. 
    
    TARGET JOB: {target_job}
    
    CURRENT PROFILE DATA (JSON):
    {str(scraped_data)[:10000]} # Truncate if too long to stay safe
    
    TASK: Optimize this LinkedIn profile specifically to attract recruiters for the TARGET JOB.
    Return ONLY a valid JSON object with the following fields:
    
    1. "headline": A punchy, SEO-optimized headline (max 220 chars).
    2. "about": A compelling 1st-person summary telling their professional story (max 200 words).
    3. "experience_bullets": A rewritten version of their most recent/relevant role's description using action verbs and metrics.
    4. "skills": A comma-separated list of top 10 skills to add for this job.
    
    Tone: Professional, confident, yet human.
    """

    model = genai.GenerativeModel('gemini-1.5-flash') # Or gemini-3-flash if available to you
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    
    return jsonify(response.text)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
import os
import csv
from http.cookiejar import MozillaCookieJar
from llama_cpp import Llama
import requests
import contextlib
import json
from urllib.parse import urlparse, parse_qs

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
model_filename = "Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf"
MODEL_PATH = os.path.join(os.getcwd(), "LLM", model_filename)
COOKIE_FILE = "indeed_cookies.txt"             # must be in cwd
QUERY = "marketing manager"
LOCATION = "remote"
PAGES = 3
CSV_FILE = "qualified_leads.csv"
CACHE_FILE = "desc_cache.json"

# -------------------------------------------------------------------
# LLM INITIALIZATION
# -------------------------------------------------------------------
print("Loading LLaMA model ...")
llm = Llama(model_path=MODEL_PATH, n_ctx=2048, n_gpu_layers=-1)
print("Model loaded!\n")

# -------------------------------------------------------------------
# COOKIE HELPERS
# -------------------------------------------------------------------
def load_cookies_from_file(cookie_path=COOKIE_FILE):
    jar = MozillaCookieJar()
    jar.load(cookie_path, ignore_discard=True, ignore_expires=True)
    cookies = []
    for c in jar:
        cookies.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain if c.domain.startswith(".") else c.domain,
            "path": c.path or "/"
        })
    return cookies

# -------------------------------------------------------------------
# SCRAPER
# -------------------------------------------------------------------
def normalize_indeed_url(job_url):
    """Return a clean /viewjob?jk=<id> URL from any Indeed redirect link."""
    try:
        parsed = urlparse(job_url)
        qs = parse_qs(parsed.query)
        if "jk" in qs and isinstance(qs["jk"], list) and len(qs["jk"]) > 0:
            jk_val = qs["jk"][0]
            clean_url = f"https://www.indeed.com/viewjob?jk={jk_val}"
            print(f"   ↪️ Normalized Indeed URL to {clean_url}")
            return clean_url
        elif "/viewjob" in parsed.path:
            print(f"   ↪️ Already a clean viewjob link: {job_url}")
            return job_url
        else:
            print(f"   ⚠️ Could not find jk param in {job_url}")
            return job_url
    except Exception as e:
        print(f"   ❌ URL normalization error: {e}")
        return job_url
    
def fetch_full_description(job_url, cookies=None, cache=None, max_retries=3):
    """
    Fetch the full job description from an Indeed job detail page.
    Includes caching, cookie conversion, and retry logic.
    """
    if not job_url:
        return ""

    # normalize tracking URL
    job_url = normalize_indeed_url(job_url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/118.0.0.0 Safari/537.36",
        "Referer": "https://www.indeed.com/",
        "Accept-Language": "en-US,en;q=0.9"
    }

    # return cached if available
    if cache and job_url in cache:
        print(f"↩️ Using cached description for {job_url}")
        return cache[job_url]

    # convert list of cookies → dict for requests
    if isinstance(cookies, list):
        cookie_dict = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}
    else:
        cookie_dict = cookies or {}

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔸 Fetching job detail (attempt {attempt}/{max_retries}): {job_url}")
            r = requests.get(job_url, headers=headers, cookies=cookie_dict, timeout=10)
            if r.status_code != 200:
                print(f"⚠️ Failed with status {r.status_code} — retrying...")
                time.sleep(2 * attempt)
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            desc_tag = soup.select_one("div#jobDescriptionText")
            if not desc_tag:
                print(f"⚠️ No job description tag found on page (attempt {attempt})")
                time.sleep(1)
                continue

            desc_text = desc_tag.get_text(" ", strip=True)
            print(f"✅ Description fetched ({len(desc_text)} chars)")

            # cache result
            if cache is not None:
                cache[job_url] = desc_text
            return desc_text

        except Exception as e:
            print(f"❌ Exception fetching description (attempt {attempt}): {e}")
            time.sleep(2 * attempt)

    print(f"❌ All attempts failed for {job_url}")
    return ""

# -------------------------------------------------------------------
# INDEED SCRAPER
# -------------------------------------------------------------------
def scrape_indeed_logged_in(query=QUERY, location=LOCATION, pages=PAGES):
    cookies = load_cookies_from_file()
    print(f"Loaded cookies from file: {COOKIE_FILE}")

    options = uc.ChromeOptions()
    # comment out next line if you want to see browser
    # options.add_argument("--headless=new")
    driver = uc.Chrome(options=options, use_subprocess=True)

    base_url = "https://www.indeed.com/"
    driver.get(base_url)
    time.sleep(1.5)

    driver.delete_all_cookies()
    for c in cookies:
        try:
            driver.add_cookie(c)
        except Exception:
            continue

    # load cached descriptions if available
    desc_cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                desc_cache = json.load(f)
        except Exception:
            desc_cache = {}

    all_jobs = []
    for page in range(pages):
        start = page * 10
        url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location}&start={start}&sort=date"
        driver.get(url)
        time.sleep(random.uniform(2.0, 3.5))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("div.job_seen_beacon, div.slider_item")

        for card in cards:
            title_tag = card.select_one("h2.jobTitle span")
            link_tag = card.select_one("h2.jobTitle a")
            company_tag = card.select_one('span[data-testid="company-name"]')
            location_tag = card.select_one('div[data-testid="text-location"] span')
            salary_tag = card.select_one('div.css-1a6kja7 span')
            perks_tag = card.select_one('ul.metadataContainer')

            title = title_tag.get_text(strip=True) if title_tag else ""
            link = (
                f"https://www.indeed.com{link_tag['href']}"
                if link_tag and link_tag.has_attr("href")
                else ""
            )
            company = company_tag.get_text(strip=True) if company_tag else ""
            location = location_tag.get_text(strip=True) if location_tag else ""
            salary = salary_tag.get_text(strip=True) if salary_tag else ""
            short_desc = perks_tag.get_text(" ", strip=True) if perks_tag else ""

            # fetch full job description
            full_desc = fetch_full_description(link, cookies=cookies, cache=desc_cache)

            job = {
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "description_short": short_desc,
                "description_full": full_desc,
                "link": link,
                "source": "Indeed",
                "pub_date": time.strftime("%Y-%m-%d"),
            }

            all_jobs.append(job)
            time.sleep(random.uniform(1.5, 2.5))

        print(f"✅ Page {page+1}: Found {len(cards)} job cards")
        time.sleep(random.uniform(1.0, 2.0))

    # save description cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(desc_cache, f, indent=2)

    with contextlib.suppress(Exception):
        driver.quit()

    print(f"✅ Found {len(all_jobs)} jobs total\n")
    return all_jobs

# -------------------------------------------------------------------
# LLaMA FILTER
# -------------------------------------------------------------------
def is_relevant(job):
    keywords = ["B2B", "SaaS", "startup", "AI", "LLM", "software", "tech"]
    text = (job["title"] + " " + job["description_full"]).lower()

    # quick keyword prefilter
    if not any(k.lower() in text for k in keywords):
        return None

    prompt = f"""
    You are a marketing lead qualifier for a digital marketing agency focused on B2B, SaaS, and tech startups.
    Rate this job posting from 0–10 based on how likely the company is in your target space (tech, AI, LLM, SaaS, B2B, startup).
    Also provide one short reason.

    Return JSON: {{"score": <number>, "reason": "<short reason>"}}

    Title: {job['title']}
    Company: {job['company']}
    Description: {job['description_full']}
    """

    try:
        output = llm(prompt, max_tokens=60, temperature=0.3, stop=["}"])
        response = output["choices"][0]["text"].strip()
        import re, json
        match = re.search(r"\{.*", response)
        if match:
            data_str = match.group(0)
            if not data_str.endswith("}"):
                data_str += "}"
            data = json.loads(data_str)
            return data
        return None
    except Exception:
        return None

# -------------------------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------------------------
def main():
    all_jobs = scrape_indeed_logged_in()
    qualified = []

    print("Evaluating jobs with LLaMA...\n")
    for job in all_jobs:
        result = is_relevant(job)
        if result and isinstance(result, dict) and result.get("score", 0) >= 6:
            job["score"] = result["score"]
            job["reason"] = result["reason"]
            qualified.append(job)
            print(f"✅ {job['title']} ({job['score']}/10) — {job['reason']}")
        else:
            print(f"❌ {job['title']}")

    if qualified:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(qualified[0].keys()))
            writer.writeheader()
            writer.writerows(qualified)
        print(f"\n🎯 Saved {len(qualified)} qualified leads to {CSV_FILE}")
    else:
        print("\nNo qualified leads found.")

if __name__ == "__main__":
    main()


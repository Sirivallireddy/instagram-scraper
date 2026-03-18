import json
import time
import os
import subprocess
import whisper
import re
from playwright.sync_api import sync_playwright

model = whisper.load_model("small")

def clean_text(text):
    return re.sub(r'[^A-Za-z0-9.,!?\'" ]+', '', text)

def download_video_and_transcribe(video_url, filename):
    try:
        audio_file = f"{filename}.wav"

        # Download video via yt_dlp
        import yt_dlp
        ydl_opts = {
            'outtmpl': f"{filename}.mp4",
            'quiet': True,
            'format': 'mp4'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Extract audio
        subprocess.run([
            "ffmpeg",
            "-y",
            "-i", f"{filename}.mp4",
            "-ac", "1",
            "-ar", "16000",
            audio_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Transcribe
        result = model.transcribe(audio_file, language="en")
        
        # Cleanup
        try:
            os.remove(f"{filename}.mp4")
            os.remove(audio_file)
        except:
            pass
            
        return clean_text(result["text"]) or "Not clear audio"

    except Exception as e:
        return f"Transcription error: {str(e)}"

def scrape_post_data(page, url):
    print(f"\nProcessing: {url}")
    page.goto(url)
    time.sleep(5) # Wait for content to load

    # CAPTION
    caption = ""
    try:
        # Try meta description first (most reliable for exact caption)
        meta_desc = page.locator('meta[name="description"]').get_attribute('content')
        if meta_desc and '"' in meta_desc:
            extracted = meta_desc.split('"', 1)[1].rsplit('"', 1)[0].strip()
            if extracted:
                caption = extracted
        
        # Fallback to DOM elements
        if not caption:
            h1s = page.locator("h1").all()
            for h1 in h1s:
                txt = h1.inner_text().strip()
                if len(txt) > 5:
                    caption = txt
                    break
    except:
        pass

    # VIDEO / IMAGE
    is_video = "/reel/" in url or "/tv/" in url
    try:
        if page.locator("video").count() > 0:
            is_video = True
    except:
        pass

    # LIKES
    likes = "Not available"
    try:
        # 1. Try meta description first
        meta_desc = page.locator('meta[name="description"]').get_attribute("content")
        if meta_desc:
            import re
            match = re.search(r'([\d,\.]+[KM]?)\s*likes?', meta_desc, re.IGNORECASE)
            if match:
                likes = match.group(1)
        
        # 2. Try DOM
        if likes == "Not available":
            for selector in ['a[href$="/liked_by/"] span', 'span:has-text(" likes")', 'section span:has-text(" likes")']:
                el = page.locator(selector).first
                if el.is_visible():
                    text = el.inner_text().strip()
                    match = re.search(r'([\d,\.]+[KM]?)\s*likes?', text, re.IGNORECASE)
                    if match:
                        likes = match.group(1)
                        break
    except:
        pass


    # COMMENTS
    comments = []
    try:
        print("Collecting comments...")
        # Scroll in the comments container or main page
        for _ in range(5):
            page.mouse.wheel(0, 2000)
            time.sleep(1.5)

        # Find typical comment elements
        comment_elements = page.locator("ul li span, div > span[dir='auto']").all()
        for e in comment_elements:
            txt = e.inner_text().strip()
            if len(txt) > 2 and txt not in comments and txt != caption:
                comments.append(txt)
            if len(comments) >= 50:
                break
                
        comments = list(set(comments))[:50]
        print(f"Collected {len(comments)} comments.")
    except Exception as e:
        print("Failed to scrape comments:", e)

    # OUTPUT DATA
    result = {
        "post_url": url,
        "is_video": is_video,
        "likes": likes,
        "comments": comments
    }

    if caption and caption not in ["Caption not available", ""]:
        result["caption"] = caption

    if is_video:
        print("Transcribing video...")
        filename = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        transcription = download_video_and_transcribe(url, filename)
        result["transcription"] = transcription

    return result

def main():
    target = input("\nEnter an Instagram username OR a post link: ").strip()
    if not target:
        print("Please provide a valid input.")
        return

    post_urls = []
    
    with sync_playwright() as p:
        # Use persistent context to reuse login details
        browser = p.chromium.launch_persistent_context(
            user_data_dir="instagram_session",
            headless=False
        )
        page = browser.new_page()

        print("\nOpening Instagram...")
        page.goto("https://www.instagram.com/")
        time.sleep(3)
        
        # Check if login is needed
        if page.locator('input[name="username"]').is_visible(timeout=3000):
            print("👉 You are not logged in. Please log in to the Instagram window.")
            input("Press ENTER here after login is complete...")

        if target.startswith("http") and "instagram.com" in target:
            # It's a specific link
            post_urls.append(target)
        else:
            # It's a username
            profile_url = f"https://www.instagram.com/{target}/"
            print(f"Visiting profile: {profile_url}")
            page.goto(profile_url)
            time.sleep(5)
            
            # Get all posts by scrolling
            print(f"Gathering ALL posts from profile. This may take a while depending on the account size...")
            previous_count = 0
            attempts_without_new = 0
            
            while attempts_without_new < 3:
                elements = page.locator('a[href*="/p/"], a[href*="/reel/"]').all()
                for el in elements:
                    href = el.get_attribute("href")
                    if href:
                        full_url = "https://www.instagram.com" + href
                        if full_url not in post_urls:
                            post_urls.append(full_url)
                
                if len(post_urls) > previous_count:
                    print(f"Found {len(post_urls)} posts so far...")
                    previous_count = len(post_urls)
                    attempts_without_new = 0
                else:
                    attempts_without_new += 1
                    
                page.mouse.wheel(0, 5000)
                time.sleep(2)
                
            print(f"Total posts gathered: {len(post_urls)}")
                    
            if not post_urls:
                print("No posts found for this user.")

        # Scrape all gathered URLs
        scraped_data = []
        for url in post_urls:
            data = scrape_post_data(page, url)
            scraped_data.append(data)

        browser.close()

    # Save to JSON
    with open("instagram_data.json", "w", encoding="utf-8") as f:
        json.dump(scraped_data, f, indent=4, ensure_ascii=False)

    print("\n✅ Done. Scraped data saved to instagram_data.json.")

if __name__ == "__main__":
    main()
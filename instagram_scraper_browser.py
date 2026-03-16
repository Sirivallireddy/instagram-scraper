from playwright.sync_api import sync_playwright
import json
import yt_dlp
import whisper

# transcription function
def transcribe_video(post_url):

    video_file = "temp_video.mp4"

    ydl_opts = {
        'outtmpl': video_file
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([post_url])

    import ffmpeg

    audio_file = "audio.mp3"

    (
        ffmpeg
        .input(video_file)
        .output(audio_file)
    .run(overwrite_output=True)
)

    model = whisper.load_model("base")
    result = model.transcribe(audio_file)

    return result["text"]


def scrape_instagram(username):

    posts = []
    post_urls = set()

    with sync_playwright() as p:

        browser = p.chromium.launch_persistent_context(
            user_data_dir="instagram_session",
            headless=False
        )

        page = browser.new_page()

        page.goto(f"https://www.instagram.com/{username}/")

        input("Login to Instagram then press ENTER here...")

        page.wait_for_timeout(5000)

        # scroll profile
        for i in range(20):

            links = page.query_selector_all("a")

            for link in links:
                href = link.get_attribute("href")

                if href and ("/p/" in href or "/reel/" in href):
                    post_urls.add("https://www.instagram.com" + href)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)

        post_urls = list(post_urls)

        print("Total posts found:", len(post_urls))

        # open posts
        for url in post_urls:

            post_page = browser.new_page()
            post_page.goto(url)

            post_page.wait_for_timeout(3000)

            caption = None
            image_url = None

            try:
                caption_tag = post_page.locator('meta[property="og:description"]').first
                caption = caption_tag.get_attribute("content")
            except:
                pass

            try:
                img_tag = post_page.locator('meta[property="og:image"]').first
                image_url = img_tag.get_attribute("content")
            except:
                pass

            is_video = "/reel/" in url
            transcription = None

            if is_video:
                print("Transcribing video:", url)
                transcription = transcribe_video(url)

            posts.append({
                "post_url": url,
                "caption": caption,
                "image_url": image_url if not is_video else None,
                "video": "yes" if is_video else None,
                "transcription": transcription
            })

            post_page.close()

        browser.close()

    with open("instagram_data.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    print("Finished. Data saved to instagram_data.json")


username = input("Enter Instagram username: ")
scrape_instagram(username)
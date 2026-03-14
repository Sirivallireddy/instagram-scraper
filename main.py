from apify_client import ApifyClient
import json
import whisper
from moviepy import VideoFileClip
import requests

# Your Apify API token (we will add it next)
APIFY_TOKEN = "apify_api_hhnnKqvfAlnYXIGQqSef3FTOg4SyF94aR1OL"

client = ApifyClient(APIFY_TOKEN)

username = "dee_scribble"

run_input = {
    "directUrls": ["https://www.instagram.com/dee_scribble/"],
    "resultsType": "posts",
    "resultsLimit": 100,
    "addParentData": True,
    "commentsLimit": 10000
}

run = client.actor("apify/instagram-scraper").call(run_input=run_input)

videos = []
def transcribe_video(video_url):
    import requests
    import whisper
    from moviepy import VideoFileClip

    video_file = "temp_video.mp4"

    # download video
    try:
        r = requests.get(video_url, timeout=30)
    except:
        print("Video download failed, skipping...")
        return None
    with open(video_file, "wb") as f:
        f.write(r.content)

    # extract audio
    clip = VideoFileClip(video_file)
    audio_file = "audio.mp3"
    clip.audio.write_audiofile(audio_file)

    # transcribe
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, task="translate")

    return result["text"]
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item.get("ownerUsername"))

    if item.get("type") != "Video":
        continue

    video_url = item.get("videoUrl")
    transcript = None

    if video_url:
        transcript = transcribe_video(video_url)

    video_data = {
        "video_url": video_url,
        "likes": item.get("likesCount"),
        "comments_count": item.get("commentsCount"),
        "comments": item.get("latestComments"),
        "transcript": transcript
    }

    videos.append(video_data)

with open("instagram_data.json", "w") as f:
    json.dump(videos, f, indent=4)

print("Data saved to instagram_data.json")
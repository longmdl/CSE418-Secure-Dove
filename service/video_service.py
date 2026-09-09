import uuid
import datetime
import ffmpeg
import subprocess
import os
from repository.video_repository import insert_video_db, get_all_videos_db, get_video_by_id_db, update_thumbnail_db

def upload_video(title, description, video_filename, author_id):
    video_id = str(uuid.uuid4()) #generate the id
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") #formatted string from datetime for create_at

    thumbnails = generate_thumbnails(video_filename, video_id)
    hls_path = generate_hls(video_filename, video_id)

    video_dict = {
        "id": video_id,
        "author_id": author_id,
        "title": title,
        "description": description,
        "video_path": "public/videos/" + video_filename,
        "created_at": created_at,
        "thumbnails": thumbnails,
        "thumbnailURL": "/" + thumbnails[0],
        "hls_path": hls_path,
    }

    insert_video_db(video_dict) #pass to repo layer
    return video_id

def get_all_videos():
    all_videos_cursor = get_all_videos_db()
    all_videos = []
    for video in all_videos_cursor:
        video.pop("_id", None)
        all_videos.append(video)
    return {"videos": all_videos}

def get_video(video_id):
    video = get_video_by_id_db(video_id)
    if video:
        video.pop("_id", None)
        return {"video": video}
    return None

def generate_thumbnails(video_filename, video_id):
    video_path = "public/videos/" + video_filename
    probe = ffmpeg.probe(video_path) 
    duration = float(probe['format']['duration']) 
    
    timestamps = [0, duration * 0.25, duration * 0.50, duration * 0.75, duration * 0.99]
    thumbnails = []
    
    os.makedirs("public/imgs/thumbnails", exist_ok=True)
    
    for i in range(len(timestamps)):
        time = timestamps[i]
        thumbnail_name = str(video_id) + "_" + str(i) + ".jpg"
        thumbnail_path = "public/imgs/thumbnails/" + thumbnail_name
        (
            ffmpeg
            .input(video_path, ss=time)
            .output(thumbnail_path, vframes=1)
            .overwrite_output()
            .run()
        )
        thumbnails.append("public/imgs/thumbnails/" + thumbnail_name)
        
    return thumbnails

def update_video_thumbnail(video_id, new_thumbnail_url, author_id):
    if not new_thumbnail_url.startswith("/"):
        new_thumbnail_url = "/" + new_thumbnail_url
        
    return update_thumbnail_db(video_id, new_thumbnail_url, author_id)

def generate_hls(video_filename, video_id):
    video_path = "public/videos/" + video_filename
    hls_directory = "public/videos/" + str(video_id) + "_" + "hls"
    
    os.makedirs(hls_directory, exist_ok=True)
    os.makedirs(hls_directory + "/144p", exist_ok=True)
    os.makedirs(hls_directory + "/720p", exist_ok=True)

    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-filter_complex", "[0:v]scale=256:144[v144];[0:v]scale=1280:720[v720]",
        "-map", "[v144]", "-map", "0:a", "-map", "[v720]", "-map", "0:a",
        "-c:v", "libx264",
        "-b:v:0", "200k",
        "-b:v:1", "2800k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-var_stream_map", "v:0,a:0,name:144p v:1,a:1,name:720p",
        "-master_pl_name", "main.m3u8",
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "0", 
        "-hls_segment_filename", hls_directory + "/%v/segment_%d.ts",
        hls_directory + "/%v/index.m3u8"
    ], check=True)

    return "/public/videos/" + str(video_id) + "_" + "hls/main.m3u8"
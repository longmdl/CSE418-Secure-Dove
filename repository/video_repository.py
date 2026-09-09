from util.database import videos_collection

def insert_video_db(video_dict):
    videos_collection.insert_one(video_dict)
    return True

def get_all_videos_db():
    all_video_cursor = videos_collection.find()
    return all_video_cursor

def get_video_by_id_db(video_id):
    exact_video_cursor = videos_collection.find_one({"id": video_id})
    return exact_video_cursor

def update_thumbnail_db(video_id, new_thumbnail_url, author_id):
    result = videos_collection.update_one({"id": video_id, "author_id": author_id},{"$set": {"thumbnailURL": new_thumbnail_url}})
    return result.matched_count > 0
from util.database import drawings_collection
from bson.objectid import ObjectId

def insert_drawing_db(drawing_dict):
    result = drawings_collection.insert_one(drawing_dict)
    return str(result.inserted_id)

def get_all_drawings_db():
    all_drawings = list(drawings_collection.find({}, {"_id": 0}))
    return all_drawings
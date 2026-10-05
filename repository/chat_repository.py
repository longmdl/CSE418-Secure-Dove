from util.database import chat_collection


# SD-10 removes the legacy global chat collection because it stored readable
# message bodies. Dropping the collection is idempotent, so it is safe to run
# each time the application starts while older databases are being migrated.
def drop_legacy_chat_database():
    chat_collection.drop()
    return

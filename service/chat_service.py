from repository.chat_repository import drop_legacy_chat_database


# SD-10 migration: the old global chat path stored readable message bodies.
# Remove that collection at startup so plaintext rows from older versions do
# not remain beside the encrypted conversation/message collections.
def remove_legacy_chat_data():
    drop_legacy_chat_database()
    return


# auth_service still calls this hook after a username change. Legacy chat rows
# no longer exist, so there is no stored author field that needs to be updated.
def update_chat_author(author_id, author_name):
    return


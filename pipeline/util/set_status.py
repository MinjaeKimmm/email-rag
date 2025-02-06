from ..common.store import EmailStore

def set_complete():
    store = EmailStore()
    store.set_embedding_status("COMPLETE")

if __name__ == "__main__":
    set_complete()

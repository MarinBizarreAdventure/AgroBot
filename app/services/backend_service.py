from app.core.backend.sync import BackendSync
from app.core.backend.client import BackendClient

class BackendService:
    def __init__(self):
        self.client = BackendClient()
        self.sync = BackendSync(self.client)

    def sync_data(self, data):
        return self.sync.sync_data(data)

    def update_status(self, status):
        return self.sync.update_status(status)

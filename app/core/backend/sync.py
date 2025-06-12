class BackendSync:
    def __init__(self, client):
        self.client = client

    def sync_data(self, data):
        # Logic to sync data with backend
        return self.client.send_data(data)

    def update_status(self, status):
        # Logic to update robot status in backend
        return self.client.update_status(status)

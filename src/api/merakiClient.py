import requests

class MerakiClient:
    def __init__(self, apiKey, organizationId):
        self.organizationId = organizationId
        self.baseUrl = "https://api.meraki.com/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "X-Cisco-Meraki-API-Key": apiKey,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def getNetworks(self):
        url = f"{self.baseUrl}/organizations/{self.organizationId}/networks"
        response = self.session.get(url)
        return response.json() if response.status_code == 200 else []

    def getUplinks(self):
        url = f"{self.baseUrl}/organizations/{self.organizationId}/uplinks/statuses"
        response = self.session.get(url)
        return response.json() if response.status_code == 200 else []

    def getLatencyHistory(self, serial):
        url = f"{self.baseUrl}/devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8"
        response = self.session.get(url, timeout=5)
        return response.json() if response.status_code == 200 else []
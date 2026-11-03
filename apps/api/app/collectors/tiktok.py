from .base import AccessNotConfigured


class TikTokCollector:
    def collect(self):
        raise AccessNotConfigured("TikTok live collection requires an authorized public source or licensed API adapter; no network request made")

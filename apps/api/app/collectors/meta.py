from .base import AccessNotConfigured


class MetaCollector:
    def collect(self):
        raise AccessNotConfigured("Meta live collection requires an authorized public source or licensed API adapter; no network request made")

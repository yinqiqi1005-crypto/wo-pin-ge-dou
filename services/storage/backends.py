from typing import BinaryIO, Protocol

from django.core.files.storage import default_storage


class StorageBackend(Protocol):
    def save(self, name: str, content) -> str: ...

    def open(self, name: str, mode: str = "rb") -> BinaryIO: ...

    def exists(self, name: str) -> bool: ...

    def delete(self, name: str) -> None: ...


class DjangoStorageBackend:
    """Small replaceable boundary around Django's configured file storage."""

    def __init__(self, storage=None):
        self.storage = storage or default_storage

    def save(self, name, content):
        return self.storage.save(name, content)

    def open(self, name, mode="rb"):
        return self.storage.open(name, mode)

    def exists(self, name):
        return self.storage.exists(name)

    def delete(self, name):
        self.storage.delete(name)

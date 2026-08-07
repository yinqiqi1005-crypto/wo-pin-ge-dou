from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage

from services.storage import DjangoStorageBackend


def test_storage_adapter_uses_replaceable_django_backend_for_file_lifecycle():
    backend = DjangoStorageBackend(InMemoryStorage())

    saved_name = backend.save("uploads/example.txt", ContentFile(b"bead-pattern"))

    assert backend.exists(saved_name)
    with backend.open(saved_name) as stored:
        assert stored.read() == b"bead-pattern"
    backend.delete(saved_name)
    assert backend.exists(saved_name) is False

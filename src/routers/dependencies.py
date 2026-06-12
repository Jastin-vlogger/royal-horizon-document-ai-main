"""Router dependencies."""

from src.containers.application_container import get_container


def dispatcher():
    """Resolve a fresh dispatcher from the application container."""

    return get_container().document_workflow_dispatcher()

"""Application dependency container."""

from dependency_injector import containers, providers

from src.brokers.document_render_broker import DocumentRenderBroker
from src.brokers.langchain_openai_broker import LangChainOpenAIBroker
from src.brokers.prompt_config_broker import PromptConfigBroker
from src.brokers.textract_broker import TextractBroker
from src.config.settings import get_settings
from src.coordination.document_workflow_coordinator_impl import (
    DocumentWorkflowCoordinator,
)
from src.dispatchers.document_workflow_dispatcher_impl import DocumentWorkflowDispatcher
from src.foundation.document_foundation_impl import DocumentFoundation
from src.foundation.llm_foundation_impl import LLMFoundation
from src.foundation.ocr_foundation_impl import OCRFoundation
from src.foundation.prompt_foundation_impl import PromptFoundation
from src.orchestration.document_workflow_orchestrator_impl import (
    DocumentWorkflowOrchestrator,
)


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency Injector container for the service."""

    config = providers.Configuration()

    settings = providers.Singleton(get_settings)

    document_render_broker = providers.Singleton(DocumentRenderBroker)
    prompt_config_broker = providers.Singleton(PromptConfigBroker)
    textract_broker = providers.Singleton(TextractBroker, settings=settings)

    langchain_openai_broker = providers.Factory(
        LangChainOpenAIBroker,
        settings=settings,
    )
    llm_broker = providers.Selector(
        config.llm_provider,
        langchain_openai=langchain_openai_broker,
    )

    document_foundation = providers.Factory(
        DocumentFoundation,
        document_broker=document_render_broker,
    )
    prompt_foundation = providers.Factory(
        PromptFoundation,
        prompt_broker=prompt_config_broker,
    )
    llm_foundation = providers.Factory(
        LLMFoundation,
        llm_broker=llm_broker,
    )
    ocr_foundation = providers.Factory(
        OCRFoundation,
        textract_broker=textract_broker,
    )

    document_workflow_orchestrator = providers.Factory(
        DocumentWorkflowOrchestrator,
        settings=settings,
        documents=document_foundation,
        llm=llm_foundation,
        prompts=prompt_foundation,
        ocr=ocr_foundation,
    )
    document_workflow_coordinator = providers.Factory(
        DocumentWorkflowCoordinator,
        orchestrator=document_workflow_orchestrator,
    )
    document_workflow_dispatcher = providers.Factory(
        DocumentWorkflowDispatcher,
        coordinator=document_workflow_coordinator,
    )


_container: ApplicationContainer | None = None


def create_container() -> ApplicationContainer:
    """Create and configure the application container."""

    container = ApplicationContainer()
    settings = get_settings()
    container.config.llm_provider.from_value(settings.llm_provider)
    return container


def get_container() -> ApplicationContainer:
    """Return process-wide application container."""

    global _container
    if _container is None:
        _container = create_container()
    return _container

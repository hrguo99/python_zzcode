"""
AI SDK Unified - Python Implementation

A unified Python SDK wrapper for multiple AI providers.
"""

from .message import (
    Message,
    Role,
    PartType,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    ReasoningPart,
    FilePart,
    Part,
    to_model_messages,
)

from .tool import (
    Tool,
    ToolRegistry,
    ToolCall,
    ToolResult,
    ToolError,
    ToolExecutionError,
    ToolValidationError,
    ToolPermissionError,
)

from .provider import ProviderManager

from .providers import (
    BaseProvider,
    ProviderRegistry,
    ProviderType,
    Model,
    ModelCapabilities,
    ModelCost,
    ModelLimits,
    StreamChunk,
    StreamResponse,
    OpenAIProvider,
    AnthropicProvider,
    GLMProvider,
    CustomProvider,
)

from .llm import (
    LLM,
    StreamOptions,
    StreamInput,
    StreamResult,
)

from .processor import (
    Session,
    SessionStatus,
    ProcessResult,
    ProcessorConfig,
    SessionProcessor,
)

from .tracker import (
    InteractionTracker,
    Interaction,
    InteractionInput,
    InteractionOutput,
)

__version__ = "0.1.0"

__all__ = [
    # Message
    "Message",
    "Role",
    "PartType",
    "TextPart",
    "ToolCallPart",
    "ToolResultPart",
    "ReasoningPart",
    "FilePart",
    "Part",
    "to_model_messages",

    # Tool
    "Tool",
    "ToolRegistry",
    "ToolCall",
    "ToolResult",
    "ToolError",
    "ToolExecutionError",
    "ToolValidationError",
    "ToolPermissionError",

    # Provider
    "ProviderManager",

    # Providers
    "BaseProvider",
    "ProviderRegistry",
    "ProviderType",
    "Model",
    "ModelCapabilities",
    "ModelCost",
    "ModelLimits",
    "StreamChunk",
    "StreamResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "GLMProvider",
    "CustomProvider",

    # LLM
    "LLM",
    "StreamOptions",
    "StreamInput",
    "StreamResult",

    # Processor
    "Session",
    "SessionStatus",
    "ProcessResult",
    "ProcessorConfig",
    "SessionProcessor",

    # Tracker
    "InteractionTracker",
    "Interaction",
    "InteractionInput",
    "InteractionOutput",
]

# Convenience function for quick usage
def create_llm(
    provider: str = "openai",
    model: str | None = None,
    track_interactions: bool = False,
    log_dir: str = "./interactions",
) -> LLM:
    """
    Create an LLM instance with optional tracking.

    Args:
        provider: Provider ID (e.g., "openai", "anthropic")
        model: Model ID (e.g., "gpt-4", "claude-3-5-sonnet-20241022")
        track_interactions: Whether to track interactions
        log_dir: Directory to save interaction logs

    Returns:
        Configured LLM instance

    Example:
        ```python
        from ai_sdk import create_llm

        llm = create_llm(provider="openai", model="gpt-4")

        response = await llm.stream(
            messages=[Message.user("Hello!")]
        )

        async for chunk in response:
            if chunk.text:
                print(chunk.text, end="")
        ```
    """
    tracker = None
    if track_interactions:
        tracker = InteractionTracker(log_dir=log_dir)

    return LLM(provider=provider, model=model, tracker=tracker)


def create_local_llm(
    base_url: str,
    model: str = "default",
    provider_name: str = "Local",
    models: dict[str, Model] | None = None,
    track_interactions: bool = False,
    log_dir: str = "./interactions",
) -> LLM:
    """
    Create an LLM instance for a local OpenAI-compatible model.

    This is a convenience function for connecting to local model servers
    like Ollama, vLLM, LocalAI, LM Studio, etc.

    Args:
        base_url: Base URL of your local model server
            - Ollama: "http://localhost:11434/v1"
            - vLLM: "http://localhost:8000/v1"
            - LocalAI: "http://localhost:8080/v1"
            - LM Studio: "http://localhost:1234/v1"
        model: Model ID to use
        provider_name: Name for this provider
        models: Optional custom model definitions
        track_interactions: Whether to track interactions
        log_dir: Directory to save interaction logs

    Returns:
        Configured LLM instance

    Example:
        ```python
        from ai_sdk import create_local_llm, Message

        # For Ollama
        llm = create_local_llm(
            base_url="http://localhost:11434/v1",
            model="llama3.2"
        )

        # For vLLM
        llm = create_local_llm(
            base_url="http://localhost:8000/v1",
            model="meta-llama/Llama-3.2-3B-Instruct"
        )

        response = await llm.generate(
            messages=[Message.user("Hello!")]
        )
        print(response.text)
        ```
    """
    tracker = None
    if track_interactions:
        tracker = InteractionTracker(log_dir=log_dir)

    # Create custom provider
    provider = CustomProvider(
        base_url=base_url,
        models=models,
        provider_name=provider_name,
    )

    # Create LLM with the custom provider
    return LLM(provider=provider.provider_id, model=model, tracker=tracker, _provider=provider)


def create_ollama_llm(
    model: str = "llama3.2",
    host: str = "http://localhost:11434",
    track_interactions: bool = False,
    log_dir: str = "./interactions",
) -> LLM:
    """
    Create an LLM instance for Ollama.

    Args:
        model: Model name (e.g., "llama3.2", "mistral", "qwen2.5")
        host: Ollama host URL
        track_interactions: Whether to track interactions
        log_dir: Directory to save interaction logs

    Returns:
        Configured LLM instance

    Example:
        ```python
        from ai_sdk import create_ollama_llm, Message

        llm = create_ollama_llm(model="llama3.2")

        response = await llm.generate(
            messages=[Message.user("Tell me a joke")]
        )
        print(response.text)
        ```
    """
    return create_local_llm(
        base_url=f"{host}/v1",
        model=model,
        provider_name="Ollama",
        track_interactions=track_interactions,
        log_dir=log_dir,
    )


def create_vllm_llm(
    model: str = "default",
    host: str = "http://localhost:8000",
    track_interactions: bool = False,
    log_dir: str = "./interactions",
) -> LLM:
    """
    Create an LLM instance for vLLM.

    Args:
        model: Model name or path
        host: vLLM server URL
        track_interactions: Whether to track interactions
        log_dir: Directory to save interaction logs

    Returns:
        Configured LLM instance

    Example:
        ```python
        from ai_sdk import create_vllm_llm, Message

        llm = create_vllm_llm(
            model="meta-llama/Llama-3.2-3B-Instruct"
        )

        response = await llm.generate(
            messages=[Message.user("Explain quantum computing")]
        )
        print(response.text)
        ```
    """
    return create_local_llm(
        base_url=f"{host}/v1",
        model=model,
        provider_name="vLLM",
        track_interactions=track_interactions,
        log_dir=log_dir,
    )

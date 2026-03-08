# model_adapter.py
# Role: Backend adapter layer bridging the legacy runtime and future queue runtime.
# Imports from: config.py, ollama_client.py, runtime_models.py
# Contract: BaseModelAdapter, OllamaModelAdapter, build_default_adapter()
# NOTE: This file does not change active runtime behavior yet. It provides a
#       stable adapter interface that future planner/executor code can depend on.

from __future__ import annotations

from abc import ABC, abstractmethod

from config import MODEL_NAME
from ollama_client import check_ollama_running, load_model, query_model_reply
from runtime_models import ModelReply


class BaseModelAdapter(ABC):
    """
    Minimal backend interface for local model runtimes.
    Future adapters (LM Studio, llama.cpp HTTP, OpenAI-compatible servers)
    should implement this same shape.
    """

    def __init__(self, default_model: str):
        self.default_model = default_model

    @property
    @abstractmethod
    def backend_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def warmup(self, model_name: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate_reply(
        self,
        prompt: str,
        system: str | None = None,
        model_name: str | None = None,
        timeout: int = 60,
    ) -> ModelReply:
        raise NotImplementedError

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        model_name: str | None = None,
        timeout: int = 60,
    ) -> str:
        return self.generate_reply(
            prompt=prompt,
            system=system,
            model_name=model_name,
            timeout=timeout,
        ).content


class OllamaModelAdapter(BaseModelAdapter):
    @property
    def backend_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        return check_ollama_running()

    def warmup(self, model_name: str | None = None) -> bool:
        return load_model(model_name or self.default_model)

    def generate_reply(
        self,
        prompt: str,
        system: str | None = None,
        model_name: str | None = None,
        timeout: int = 60,
    ) -> ModelReply:
        selected_model = model_name or self.default_model
        reply = query_model_reply(
            prompt=prompt,
            system=system,
            model_name=selected_model,
            timeout=timeout,
        )
        reply.metadata["adapter"] = self.backend_name
        return reply



def build_default_adapter() -> BaseModelAdapter:
    return OllamaModelAdapter(default_model=MODEL_NAME)

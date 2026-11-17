"""Builds the shared service objects used by the UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from config import Settings
from database.chat_database import ChatDatabase
from models.model_registry import ModelRegistry
from services.chat_service import ChatService
from services.key_store import KeyStore
from services.model_service import ModelService
from services.openrouter_client import OpenRouterClient


@dataclass
class Services:
    settings: Settings
    db: ChatDatabase
    registry: ModelRegistry
    key_store: KeyStore
    model_service: ModelService
    chat_service: ChatService
    client_factory: Callable[[str], OpenRouterClient]


def build_services(settings: Settings) -> Services:
    db = ChatDatabase(settings.db_path)
    registry = ModelRegistry(settings.builtin_models_path, settings.user_models_path)
    key_store = KeyStore(settings.openrouter_api_key)

    def client_factory(key: str) -> OpenRouterClient:
        return OpenRouterClient(key, settings.openrouter_base_url, settings.request_timeout)

    model_service = ModelService(lambda: client_factory(""))
    chat_service = ChatService(db, key_store, client_factory)
    return Services(settings, db, registry, key_store, model_service, chat_service, client_factory)

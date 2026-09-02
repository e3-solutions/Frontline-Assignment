"""Supabase client service for database operations."""

import os

from loguru import logger
from supabase import Client, create_client


class SupabaseService:
    """Singleton Supabase client - auto-initializes on first use."""

    _instance: Client | None = None

    @classmethod
    def get_client(cls) -> Client:
        """Get the Supabase client, initializing if needed."""
        if cls._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
            cls._instance = create_client(url, key)
            logger.info("Supabase client initialized")
        return cls._instance

    @classmethod
    def initialize(cls) -> None:
        """Explicit init (for app startup). Auto-inits anyway on first use."""
        cls.get_client()

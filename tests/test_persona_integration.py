#!/usr/bin/env python3
"""
Test suite for PMOVES Agent Zero Persona Integration.

Tests cover:
- Configuration validation with missing credentials
- Data model validation (PersonaConfig, PersonaEnhancement)
- ThreadType enum functionality
- Field validation in from_supabase_row
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from python.helpers.persona_integration import (
    ThreadType,
    PersonaConfig,
    PersonaEnhancement,
    PersonaAgentRequest,
    PersonaIntegrationError,
    SupabaseConnectionError,
    PersonaIntegrationService
)


# ============================================================================
# ThreadType Tests
# ============================================================================

class TestThreadType:
    """Test ThreadType StrEnum functionality."""

    def test_all_thread_types_defined(self):
        """Verify all expected thread types are defined."""
        expected_types = ["base", "parallel", "chained", "fusion", "big", "zero_touch"]
        actual_types = [t.value for t in ThreadType]

        for expected in expected_types:
            assert expected in actual_types, f"ThreadType.{expected.upper()} not defined"

    def test_thread_type_is_string(self):
        """ThreadType members should be string-compatible."""
        assert str(ThreadType.BASE) == "base"
        assert ThreadType.BASE == "base"
        assert ThreadType.BASE in ["base", "parallel"]


# ============================================================================
# PersonaConfig Tests
# ============================================================================

class TestPersonaConfig:
    """Test PersonaConfig dataclass."""

    def test_from_supabase_row_missing_required_field(self):
        """from_supabase_row should raise ValueError for missing required fields."""
        # Missing persona_id
        with pytest.raises(ValueError, match="Missing required field"):
            PersonaConfig.from_supabase_row({
                "name": "Test",
                "version": "1.0"
            })

        # Missing name
        with pytest.raises(ValueError, match="Missing required field"):
            PersonaConfig.from_supabase_row({
                "persona_id": "uuid-123",
                "version": "1.0"
            })

        # Missing version
        with pytest.raises(ValueError, match="Missing required field"):
            PersonaConfig.from_supabase_row({
                "persona_id": "uuid-123",
                "name": "Test"
            })

    def test_from_supabase_row_valid_data(self):
        """from_supabase_row should create valid PersonaConfig from complete row."""
        row = {
            "persona_id": "test-uuid-123",
            "name": "Developer",
            "version": "1.0",
            "description": "Software engineering specialist",
            "thread_type": "chained",
            "model_preference": "claude-sonnet-4-5",
            "temperature": 0.7,
            "max_tokens": 4096,
            "system_prompt_template": "You are a developer.",
            "tools_access": ["mcp", "search"],
            "behavior_weights": {"decode": 0.3, "retrieve": 0.3, "generate": 0.4},
            "nats_subjects": ["agents.>"],
            "default_packs": ["python", "javascript"],
            "boosts": ["code-review"],
            "filters": ["no-pii"],
            "eval_gates": ["security-check"],
            "is_active": True
        }

        persona = PersonaConfig.from_supabase_row(row)

        assert persona.persona_id == "test-uuid-123"
        assert persona.name == "Developer"
        assert persona.thread_type == ThreadType.CHAINED
        assert persona.temperature == 0.7


# ============================================================================
# PersonaEnhancement Tests
# ============================================================================

class TestPersonaEnhancement:
    """Test PersonaEnhancement dataclass."""

    def test_from_supabase_row_valid_data(self):
        """from_supabase_row should create valid PersonaEnhancement."""
        row = {
            "enhancement_id": "enh-uuid-123",
            "persona_id": "persona-uuid",
            "enhancement_type": "tool",
            "enhancement_name": "code-review-access",
            "enhancement_value": {"permission": "write"},
            "priority": 5,
            "metadata": {"added_by": "admin"}
        }

        enhancement = PersonaEnhancement.from_supabase_row(row)

        assert enhancement.enhancement_id == "enh-uuid-123"
        assert enhancement.enhancement_type == "tool"
        assert enhancement.priority == 5
        assert enhancement.enhancement_value == {"permission": "write"}


# ============================================================================
# PersonaIntegrationService Tests
# ============================================================================

class TestPersonaIntegrationServiceInit:
    """Test PersonaIntegrationService initialization."""

    def test_init_without_credentials_raises_error(self, monkeypatch):
        """Service should raise ValueError when Supabase credentials are missing."""
        # Remove environment variables
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured"):
            PersonaIntegrationService()

    def test_init_with_partial_credentials_raises_error(self, monkeypatch):
        """Service should raise ValueError when only one credential is provided."""
        monkeypatch.setenv("SUPABASE_URL", "http://localhost:8000")
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured"):
            PersonaIntegrationService()

    def test_init_with_full_credentials_succeeds(self, monkeypatch):
        """Service should initialize successfully with full credentials."""
        monkeypatch.setenv("SUPABASE_URL", "http://localhost:8000")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key-123")

        service = PersonaIntegrationService()
        assert service.supabase_url == "http://localhost:8000"
        assert service.supabase_key == "test-key-123"


# ============================================================================
# PersonaAgentRequest Tests
# ============================================================================

class TestPersonaAgentRequest:
    """Test PersonaAgentRequest Pydantic model."""

    def test_valid_request(self):
        """Should create valid request with all fields."""
        request = PersonaAgentRequest(
            persona_id="test-uuid",
            context_allocation=0.5,
            parent_agent_id="parent-uuid",
            overrides={"model": "claude-opus-4-5"},
            enhancement_ids=["enh1", "enh2"]
        )

        assert request.persona_id == "test-uuid"
        assert request.context_allocation == 0.5
        assert request.overrides["model"] == "claude-opus-4-5"

    def test_minimal_request(self):
        """Should create valid request with only required field."""
        request = PersonaAgentRequest(persona_id="test-uuid")

        assert request.persona_id == "test-uuid"
        assert request.context_allocation == 0.3  # default
        assert request.parent_agent_id is None  # default
        assert request.overrides is None  # default

    def test_context_allocation_bounds(self):
        """Should validate context_allocation is between 0 and 1."""
        # Valid values
        PersonaAgentRequest(persona_id="test", context_allocation=0.0)
        PersonaAgentRequest(persona_id="test", context_allocation=0.5)
        PersonaAgentRequest(persona_id="test", context_allocation=1.0)

        # Invalid values
        with pytest.raises(Exception):  # Pydantic validation error
            PersonaAgentRequest(persona_id="test", context_allocation=-0.1)

        with pytest.raises(Exception):  # Pydantic validation error
            PersonaAgentRequest(persona_id="test", context_allocation=1.1)


# ============================================================================
# Exception Hierarchy Tests
# ============================================================================

class TestExceptions:
    """Test custom exception hierarchy."""

    def test_persona_integration_error_is_exception(self):
        """PersonaIntegrationError should inherit from Exception."""
        error = PersonaIntegrationError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_supabase_connection_error_is_persona_integration_error(self):
        """SupabaseConnectionError should inherit from PersonaIntegrationError."""
        error = SupabaseConnectionError("connection failed")
        assert isinstance(error, PersonaIntegrationError)
        assert isinstance(error, Exception)
        assert "connection failed" in str(error)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

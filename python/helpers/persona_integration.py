"""
PMOVES Agent Zero - Persona Integration Module

This module provides functionality for creating agents from persona configurations
stored in Supabase. Personas define agent behavior, capabilities, and personality.

Key Concepts:
- Thread Types: base, parallel, chained, fusion, big, zero_touch
- Behavior Weights: decode, retrieve, generate balance for form selection
- Enhancements: Modular persona modifications stored separately

Integration Points:
- Supabase: Persona and enhancement storage
- NATS: Event publication for persona events
- TensorZero: Model routing via model_preference
"""

import asyncio
import json
import logging
import os
from copy import copy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

from enum import StrEnum


class ThreadType(StrEnum):
    """Agent orchestration pattern types."""
    BASE = "base"
    PARALLEL = "parallel"
    CHAINED = "chained"
    FUSION = "fusion"
    BIG = "big"
    ZERO_TOUCH = "zero_touch"


@dataclass
class PersonaConfig:
    """
    Persona configuration loaded from Supabase.

    Attributes:
        persona_id: Unique identifier for the persona
        name: Human-readable persona name
        version: Persona version string
        description: What this persona does
        thread_type: Orchestration pattern (base, parallel, etc.)
        model_preference: Default LLM model
        temperature: Generation temperature (0.0-2.0)
        max_tokens: Maximum tokens for generation
        system_prompt_template: System prompt template
        tools_access: List of tools this persona can access
        behavior_weights: Weights for form selection (decode/retrieve/generate)
        nats_subjects: NATS subjects to subscribe to
        default_packs: Grounding packs for knowledge retrieval
        boosts: Entity/topic boosts for retrieval
        filters: Content filters
        eval_gates: Quality gate thresholds
    """
    persona_id: str
    name: str
    version: str
    description: str
    thread_type: str = ThreadType.BASE
    model_preference: str = "claude-sonnet-4-5"
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt_template: Optional[str] = None
    tools_access: List[str] = field(default_factory=list)
    behavior_weights: Dict[str, float] = field(default_factory=lambda: {
        "decode": 0.33,
        "retrieve": 0.34,
        "generate": 0.33
    })
    nats_subjects: List[str] = field(default_factory=list)
    default_packs: List[str] = field(default_factory=list)
    boosts: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    eval_gates: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_supabase_row(cls, row: Dict[str, Any]) -> "PersonaConfig":
        """Create PersonaConfig from Supabase row data."""
        # Validate required fields
        required_fields = ("persona_id", "name", "version")
        for field_name in required_fields:
            if field_name not in row:
                raise ValueError(f"Missing required field '{field_name}' in persona row: {row}")

        # Parse runtime JSONB if present (v5.12 compatibility)
        runtime = row.get("runtime", {}) or {}

        return cls(
            persona_id=str(row["persona_id"]),
            name=row["name"],
            version=row["version"],
            description=row.get("description", ""),
            thread_type=row.get("thread_type", runtime.get("thread_type", "base")),
            model_preference=row.get("model_preference", runtime.get("model", "claude-sonnet-4-5")),
            temperature=row.get("temperature", runtime.get("temperature", 0.7)),
            max_tokens=row.get("max_tokens", runtime.get("max_tokens", 4096)),
            system_prompt_template=row.get("system_prompt_template") or runtime.get("system_prompt"),
            tools_access=row.get("tools_access", runtime.get("tools", [])),
            behavior_weights=row.get("behavior_weights", runtime.get("weights", {})) or {
                "decode": 0.33, "retrieve": 0.34, "generate": 0.33
            },
            nats_subjects=row.get("nats_subjects", runtime.get("nats_subscriptions", [])),
            default_packs=row.get("default_packs", runtime.get("default_packs", [])),
            boosts=row.get("boosts", runtime.get("boosts", {})) or {},
            filters=row.get("filters", runtime.get("filters", {})) or {},
            eval_gates=row.get("eval_gates", runtime.get("eval_gates", {})) or {}
        )


@dataclass
class PersonaEnhancement:
    """Modular enhancement for a persona."""
    enhancement_id: str
    persona_id: str
    enhancement_type: str  # prompt, tool, weight, nats, model, eval, geometry, voice
    enhancement_name: str
    enhancement_value: Dict[str, Any]
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_supabase_row(cls, row: Dict[str, Any]) -> "PersonaEnhancement":
        """Create PersonaEnhancement from Supabase row data."""
        return cls(
            enhancement_id=str(row["enhancement_id"]),
            persona_id=str(row["persona_id"]),
            enhancement_type=row["enhancement_type"],
            enhancement_name=row["enhancement_name"],
            enhancement_value=row["enhancement_value"],
            priority=row.get("priority", 0),
            metadata=row.get("metadata", {})
        )


@dataclass
class AgentConfig:
    """
    Agent configuration derived from persona.

    This is the config passed to Agent Zero's agent creation.
    """
    name: str
    specialization: str
    thread_type: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt: Optional[str]
    tools: List[str]
    behavior_weights: Dict[str, float]
    nats_subscriptions: List[str]
    grounding_packs: List[str]
    boosts: Dict[str, Any]
    filters: Dict[str, Any]
    context_allocation: float = 0.3
    parent_agent_id: Optional[str] = None
    persona_id: Optional[str] = None


class PersonaAgentRequest(BaseModel):
    """Request model for creating agent from persona."""
    persona_id: str = Field(..., description="Persona ID from Supabase")
    context_allocation: float = Field(0.3, ge=0.0, le=1.0, description="Context window allocation")
    parent_agent_id: Optional[str] = Field(None, description="Parent agent ID for subordinate creation")
    overrides: Optional[Dict[str, Any]] = Field(None, description="Runtime overrides")
    enhancement_ids: Optional[List[str]] = Field(None, description="Specific enhancement IDs to apply")


class PersonaAgentResponse(BaseModel):
    """Response model for agent creation."""
    agent_id: str
    config: AgentConfig
    persona: PersonaConfig
    enhancements_applied: List[PersonaEnhancement]
    created_at: datetime


# ============================================================================
# Persona Integration Service
# ============================================================================

class PersonaIntegrationService:
    """
    Service for integrating personas with Agent Zero agent creation.

    Fetches persona data from Supabase and creates agent configurations
    that can be used to spawn specialized subordinate agents.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        nats_url: Optional[str] = None
    ):
        """
        Initialize the persona integration service.

        Args:
            supabase_url: Supabase API URL (from SUPABASE_URL env var)
            supabase_key: Supabase service key (from SUPABASE_SERVICE_ROLE_KEY env var)
            nats_url: NATS connection URL (from NATS_URL env var)

        Raises:
            ValueError: If Supabase credentials are not configured
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")

        # Validate Supabase configuration
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured "
                "(via environment variables or constructor parameters)"
            )

        # HTTP client for Supabase
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }
            self._client = httpx.AsyncClient(
                base_url=self.supabase_url,
                headers=headers,
                timeout=30.0
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_persona(self, persona_id: str) -> Optional[PersonaConfig]:
        """
        Fetch a persona by ID from Supabase.

        Args:
            persona_id: UUID of the persona to fetch

        Returns:
            PersonaConfig if found, None otherwise
        """
        try:
            response = await self.client.get(
                "/rest/v1/personas",
                params={
                    "persona_id": f"eq.{persona_id}",
                    "select": "*"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            return PersonaConfig.from_supabase_row(data[0])
        except Exception as e:
            logger.error("Error fetching persona %s: %s", persona_id, e)
            return None

    async def get_persona_by_name(self, name: str, version: str = "1.0") -> Optional[PersonaConfig]:
        """
        Fetch a persona by name and version.

        Args:
            name: Persona name
            version: Persona version (default: "1.0")

        Returns:
            PersonaConfig if found, None otherwise
        """
        try:
            response = await self.client.get(
                "/rest/v1/personas",
                params={
                    "name": f"eq.{name}",
                    "version": f"eq.{version}",
                    "select": "*"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            return PersonaConfig.from_supabase_row(data[0])
        except Exception as e:
            logger.error("Error fetching persona %s@%s: %s", name, version, e)
            return None

    async def list_personas(self, active_only: bool = True) -> List[PersonaConfig]:
        """
        List all personas.

        Args:
            active_only: Only return active personas

        Returns:
            List of PersonaConfig
        """
        try:
            params = {"select": "*"}
            if active_only:
                params["is_active"] = "eq.true"

            response = await self.client.get(
                "/rest/v1/personas",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            return [PersonaConfig.from_supabase_row(row) for row in data]
        except Exception as e:
            logger.error("Error listing personas: %s", e)
            return []

    async def get_enhancements(
        self,
        persona_id: str,
        enhancement_types: Optional[List[str]] = None,
        enhancement_ids: Optional[List[str]] = None
    ) -> List[PersonaEnhancement]:
        """
        Fetch enhancements for a persona.

        Args:
            persona_id: Persona ID
            enhancement_types: Optional filter by enhancement types
            enhancement_ids: Optional filter by specific enhancement IDs

        Returns:
            List of PersonaEnhancement, sorted by priority (desc)
        """
        try:
            params = {
                "persona_id": f"eq.{persona_id}",
                "select": "*",
                "order": "priority.desc"
            }

            if enhancement_types:
                params["enhancement_type"] = f"in.({','.join(enhancement_types)})"

            # Server-side filtering by enhancement_ids for efficiency
            if enhancement_ids:
                params["enhancement_id"] = f"in.({','.join(enhancement_ids)})"

            response = await self.client.get(
                "/rest/v1/persona_enhancements",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            return [PersonaEnhancement.from_supabase_row(row) for row in data]
        except Exception as e:
            logger.error("Error fetching enhancements for persona %s: %s", persona_id, e)
            return []

    def apply_enhancements(
        self,
        persona: PersonaConfig,
        enhancements: List[PersonaEnhancement]
    ) -> PersonaConfig:
        """
        Apply enhancements to a persona configuration.

        Enhancements are applied in priority order (highest first).
        Later enhancements of the same type override earlier ones.

        Args:
            persona: Base persona configuration
            enhancements: List of enhancements to apply

        Returns:
            Enhanced PersonaConfig (a copy, original is not mutated)
        """
        # Sort by priority (desc)
        sorted_enhancements = sorted(enhancements, key=lambda e: e.priority, reverse=True)

        # Create a copy to avoid mutating the original persona
        enhanced = replace(persona)
        # Clone mutable fields to avoid shared references
        enhanced.tools_access = list(persona.tools_access)
        enhanced.nats_subjects = list(persona.nats_subjects)
        enhanced.behavior_weights = dict(persona.behavior_weights)
        if persona.system_prompt_template:
            enhanced.system_prompt_template = persona.system_prompt_template

        for enhancement in sorted_enhancements:
            value = enhancement.enhancement_value

            if enhancement.enhancement_type == "model":
                enhanced.model_preference = value.get("model", enhanced.model_preference)

            elif enhancement.enhancement_type == "weight":
                enhanced.behavior_weights.update(value.get("weights", {}))

            elif enhancement.enhancement_type == "tool":
                # Add or extend tools access
                tools = value.get("tools", [])
                if value.get("append", False):
                    enhanced.tools_access.extend(t for t in tools if t not in enhanced.tools_access)
                else:
                    enhanced.tools_access = tools

            elif enhancement.enhancement_type == "nats":
                # Add NATS subscriptions
                subjects = value.get("subjects", [])
                enhanced.nats_subjects.extend(s for s in subjects if s not in enhanced.nats_subjects)

            elif enhancement.enhancement_type == "prompt":
                # Append to system prompt template
                prompt_addition = value.get("prompt", "")
                if enhanced.system_prompt_template:
                    enhanced.system_prompt_template += "\n\n" + prompt_addition
                else:
                    enhanced.system_prompt_template = prompt_addition

            elif enhancement.enhancement_type == "geometry":
                # CHIT geometry integration
                enhanced.system_prompt_template = self._apply_geometry_enhancement(
                    enhanced.system_prompt_template or "", value
                )

            elif enhancement.enhancement_type == "voice":
                # Voice persona settings (handled separately by voice service)
                enhanced.system_prompt_template = self._apply_voice_enhancement(
                    enhanced.system_prompt_template or "", value
                )

        return enhanced

    def _apply_geometry_enhancement(self, prompt: str, value: Dict[str, Any]) -> str:
        """Apply CHIT geometry awareness to prompt."""
        geometry_addition = f"""
## CHIT Geometry Integration

You have access to CHIT (Compressed Hyper-dimensional Intelligence Transport) geometry:
- Use `geometry.jump` to navigate to related content via shape anchors
- Use `geometry.decode_text` to extract meaning from geometric encodings
- Default shape context: {value.get("default_shape_id", "none")}
- Decode mode: {value.get("decode_mode", "exact")}
"""
        return prompt + geometry_addition

    def _apply_voice_enhancement(self, prompt: str, value: Dict[str, Any]) -> str:
        """Apply voice persona settings to prompt."""
        voice_addition = f"""
## Voice Persona Settings

When generating text to be spoken:
- Speaking rate: {value.get("speaking_rate", 1.0)}x
- Pitch shift: {value.get("pitch_shift", 0.0)}
- Personality traits: {', '.join(value.get("personality_traits", []))}
"""
        return prompt + voice_addition

    async def create_agent_config(
        self,
        request: PersonaAgentRequest
    ) -> Optional[AgentConfig]:
        """
        Create agent configuration from persona request.

        Args:
            request: Persona agent creation request

        Returns:
            AgentConfig if persona found, None otherwise
        """
        # Fetch persona
        persona = await self.get_persona(request.persona_id)
        if not persona:
            return None

        # Fetch enhancements with server-side filtering if IDs provided
        enhancements = await self.get_enhancements(
            request.persona_id,
            enhancement_ids=request.enhancement_ids
        )

        # Apply enhancements to persona
        enhanced_persona = self.apply_enhancements(persona, enhancements)

        # Apply runtime overrides
        if request.overrides:
            if "model" in request.overrides:
                enhanced_persona.model_preference = request.overrides["model"]
            if "temperature" in request.overrides:
                enhanced_persona.temperature = request.overrides["temperature"]
            if "max_tokens" in request.overrides:
                enhanced_persona.max_tokens = request.overrides["max_tokens"]
            if "tools" in request.overrides:
                enhanced_persona.tools_access = request.overrides["tools"]

        # Build system prompt
        system_prompt = self._build_system_prompt(enhanced_persona)

        # Create agent config
        config = AgentConfig(
            name=enhanced_persona.name,
            specialization=enhanced_persona.description,
            thread_type=enhanced_persona.thread_type,
            model=enhanced_persona.model_preference,
            temperature=enhanced_persona.temperature,
            max_tokens=enhanced_persona.max_tokens,
            system_prompt=system_prompt,
            tools=enhanced_persona.tools_access,
            behavior_weights=enhanced_persona.behavior_weights,
            nats_subscriptions=enhanced_persona.nats_subjects,
            grounding_packs=enhanced_persona.default_packs,
            boosts=enhanced_persona.boosts,
            filters=enhanced_persona.filters,
            context_allocation=request.context_allocation,
            parent_agent_id=request.parent_agent_id,
            persona_id=request.persona_id
        )

        return config

    def _build_system_prompt(self, persona: PersonaConfig) -> str:
        """Build complete system prompt from persona configuration."""
        base = persona.system_prompt_template or f"You are {persona.name}, {persona.description}."

        # Add tools section
        if persona.tools_access:
            tools_list = "\n".join(f"- {tool}" for tool in persona.tools_access)
            tools_section = f"""

## Available Tools

You have access to the following tools:
{tools_list}
"""
        else:
            tools_section = ""

        # Add grounding packs section
        if persona.default_packs:
            packs_list = "\n".join(f"- {pack}" for pack in persona.default_packs)
            grounding_section = f"""

## Knowledge Access

You can retrieve information from these grounding packs:
{packs_list}
"""
        else:
            grounding_section = ""

        # Add boosts section
        if persona.boosts:
            boosts_json = json.dumps(persona.boosts, indent=2)
            boosts_section = f"""

## Retrieval Boosts

Prioritize these entities and topics in retrieval:
{boosts_json}
"""
        else:
            boosts_section = ""

        # Add filters section
        if persona.filters:
            filters_json = json.dumps(persona.filters, indent=2)
            filters_section = f"""

## Content Filters

Apply these filters to retrieved content:
{filters_json}
"""
        else:
            filters_section = ""

        return base + tools_section + grounding_section + boosts_section + filters_section

    async def publish_persona_event(
        self,
        event_type: str,
        persona: PersonaConfig,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Publish a persona-related event to NATS.

        Args:
            event_type: Event type (e.g., "persona.agent.created.v1")
            persona: The persona
            metadata: Additional metadata
        """
        # This would require NATS connection
        # For now, just log the event
        event = {
            "event": event_type,
            "persona_id": persona.persona_id,
            "name": persona.name,
            "version": persona.version,
            "thread_type": persona.thread_type,
            "model": persona.model_preference,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {})
        }
        logger.info("Persona Event: %s\n%s", event_type, json.dumps(event, indent=2))


# ============================================================================
# Utility Functions
# ============================================================================

async def create_agent_from_persona(
    persona_id: str,
    context_allocation: float = 0.3,
    parent_agent_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    enhancement_ids: Optional[List[str]] = None
) -> Optional[AgentConfig]:
    """
    Convenience function to create agent config from persona.

    Args:
        persona_id: Persona ID from Supabase
        context_allocation: Context window allocation (0.0-1.0)
        parent_agent_id: Optional parent agent ID
        overrides: Optional runtime parameter overrides
        enhancement_ids: Optional specific enhancement IDs to apply

    Returns:
        AgentConfig if persona found, None otherwise
    """
    service = PersonaIntegrationService()
    try:
        request = PersonaAgentRequest(
            persona_id=persona_id,
            context_allocation=context_allocation,
            parent_agent_id=parent_agent_id,
            overrides=overrides,
            enhancement_ids=enhancement_ids
        )
        return await service.create_agent_config(request)
    finally:
        await service.close()


async def list_available_personas(active_only: bool = True) -> List[PersonaConfig]:
    """
    List all available personas.

    Args:
        active_only: Only return active personas

    Returns:
        List of PersonaConfig
    """
    service = PersonaIntegrationService()
    try:
        return await service.list_personas(active_only=active_only)
    finally:
        await service.close()


# ============================================================================
# CLI Entry Point
# ============================================================================

async def main():
    """CLI entry point for testing persona integration."""
    import sys

    service = PersonaIntegrationService()

    try:
        if len(sys.argv) > 1:
            command = sys.argv[1]

            if command == "list":
                personas = await service.list_personas()
                print(f"Found {len(personas)} personas:")
                for p in personas:
                    print(f"  - {p.name}@{p.version} ({p.thread_type}) - {p.description}")

            elif command == "get":
                if len(sys.argv) > 2:
                    persona_id = sys.argv[2]
                    persona = await service.get_persona(persona_id)
                    if persona:
                        print(f"Persona: {persona.name}@{persona.version}")
                        print(f"  Thread Type: {persona.thread_type}")
                        print(f"  Model: {persona.model_preference}")
                        print(f"  Tools: {', '.join(persona.tools_access)}")
                    else:
                        print(f"Persona {persona_id} not found")
                else:
                    print("Usage: python persona_integration.py get <persona_id>")

            elif command == "test-config":
                # Test creating agent config from first persona
                personas = await service.list_personas()
                if personas:
                    persona = personas[0]
                    print(f"Testing config creation from persona: {persona.name}")

                    request = PersonaAgentRequest(
                        persona_id=persona.persona_id,
                        context_allocation=0.3
                    )

                    config = await service.create_agent_config(request)
                    if config:
                        print(f"Created agent config:")
                        print(f"  Name: {config.name}")
                        print(f"  Model: {config.model}")
                        print(f"  Thread Type: {config.thread_type}")
                        print(f"  Tools: {', '.join(config.tools)}")
                    else:
                        print("Failed to create config")
                else:
                    print("No personas found")

            else:
                print("Usage:")
                print("  python persona_integration.py list")
                print("  python persona_integration.py get <persona_id>")
                print("  python persona_integration.py test-config")
        else:
            print("Usage:")
            print("  python persona_integration.py list")
            print("  python persona_integration.py get <persona_id>")
            print("  python persona_integration.py test-config")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
PMOVES Agent Zero - Persona-based Agent Creation API

MCP API endpoint for creating subordinate agents from persona configurations.
This integrates with the persona system in Supabase and allows for dynamic
agent creation based on persona definitions.

Endpoints:
- POST /api/persona/agent/create - Create agent from persona
- GET /api/persona/list - List available personas
- GET /api/persona/{id} - Get persona details
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import the persona integration helper
try:
    from ..helpers.persona_integration import (
        PersonaConfig,
        PersonaAgentRequest,
        PersonaIntegrationService,
        create_agent_from_persona,
        list_available_personas
    )
except ImportError:
    # Fallback for direct testing
    import sys
    sys.path.insert(0, "/home/pmoves/PMOVES.AI/PMOVES-Agent-Zero/python")
    from helpers.persona_integration import (
        PersonaConfig,
        PersonaAgentRequest,
        PersonaIntegrationService,
        create_agent_from_persona,
        list_available_personas
    )

router = APIRouter(prefix="/api/persona", tags=["persona"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateAgentFromPersonaRequest(BaseModel):
    """Request model for creating agent from persona."""
    persona_id: str = Field(..., description="Persona ID from Supabase")
    context_allocation: float = Field(0.3, ge=0.0, le=1.0, description="Context window allocation")
    parent_agent_id: Optional[str] = Field(None, description="Parent agent ID for subordinate creation")
    overrides: Optional[Dict[str, Any]] = Field(None, description="Runtime parameter overrides")
    enhancement_ids: Optional[List[str]] = Field(None, description="Specific enhancement IDs to apply")
    create_subordinate: bool = Field(True, description="Whether to create the subordinate agent")


class CreateAgentFromPersonaResponse(BaseModel):
    """Response model for agent creation."""
    success: bool
    agent_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    persona: Optional[Dict[str, Any]] = None
    enhancements_applied: List[Dict[str, Any]] = Field(default_factory=list)
    message: str


class PersonaListResponse(BaseModel):
    """Response model for persona list."""
    personas: List[Dict[str, Any]]
    count: int


class PersonaDetailResponse(BaseModel):
    """Response model for persona details."""
    persona: Dict[str, Any]
    enhancements: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/agent/create", response_model=CreateAgentFromPersonaResponse)
async def create_agent_from_persona_endpoint(request: CreateAgentFromPersonaRequest):
    """
    Create a subordinate agent from persona configuration.

    This endpoint:
    1. Fetches the persona from Supabase
    2. Applies any specified enhancements
    3. Builds agent configuration from persona settings
    4. Optionally creates the subordinate agent

    Request Body:
    {
        "persona_id": "uuid",
        "context_allocation": 0.3,
        "parent_agent_id": "uuid (optional)",
        "overrides": {
            "model": "claude-opus-4-5",
            "temperature": 0.5
        },
        "enhancement_ids": ["uuid1", "uuid2"],
        "create_subordinate": true
    }

    Response:
    {
        "success": true,
        "agent_id": "uuid",
        "config": { ... },
        "persona": { ... },
        "enhancements_applied": [ ... ],
        "message": "Agent created successfully"
    }
    """
    service = PersonaIntegrationService()

    try:
        # Fetch persona
        persona = await service.get_persona(request.persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {request.persona_id} not found")

        # Fetch enhancements
        if request.enhancement_ids:
            all_enhancements = await service.get_enhancements(request.persona_id)
            enhancements = [e for e in all_enhancements if e.enhancement_id in request.enhancement_ids]
        else:
            enhancements = await service.get_enhancements(request.persona_id)

        # Apply enhancements
        enhanced_persona = service.apply_enhancements(persona, enhancements)

        # Apply overrides
        if request.overrides:
            if "model" in request.overrides:
                enhanced_persona.model_preference = request.overrides["model"]
            if "temperature" in request.overrides:
                enhanced_persona.temperature = request.overrides["temperature"]
            if "max_tokens" in request.overrides:
                enhanced_persona.max_tokens = request.overrides["max_tokens"]

        # Build agent config
        config = await service.create_agent_config(
            PersonaAgentRequest(
                persona_id=request.persona_id,
                context_allocation=request.context_allocation,
                parent_agent_id=request.parent_agent_id,
                overrides=request.overrides,
                enhancement_ids=request.enhancement_ids
            )
        )

        if not config:
            raise HTTPException(status_code=500, detail="Failed to create agent config")

        # Create subordinate agent if requested
        agent_id = None
        if request.create_subordinate:
            # TODO: Integrate with actual Agent Zero agent creation
            # For now, generate a placeholder ID
            import uuid
            agent_id = str(uuid.uuid4())

            # Publish persona event
            await service.publish_persona_event(
                "persona.agent.created.v1",
                enhanced_persona,
                {
                    "agent_id": agent_id,
                    "context_allocation": request.context_allocation,
                    "parent_agent_id": request.parent_agent_id
                }
            )

        return CreateAgentFromPersonaResponse(
            success=True,
            agent_id=agent_id,
            config={
                "name": config.name,
                "specialization": config.specialization,
                "thread_type": config.thread_type,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "tools": config.tools,
                "behavior_weights": config.behavior_weights,
                "nats_subscriptions": config.nats_subscriptions,
                "grounding_packs": config.grounding_packs
            },
            persona={
                "persona_id": enhanced_persona.persona_id,
                "name": enhanced_persona.name,
                "version": enhanced_persona.version,
                "description": enhanced_persona.description,
                "thread_type": enhanced_persona.thread_type,
                "model_preference": enhanced_persona.model_preference
            },
            enhancements_applied=[
                {
                    "enhancement_id": e.enhancement_id,
                    "type": e.enhancement_type,
                    "name": e.enhancement_name
                }
                for e in enhancements
            ],
            message=f"Agent {'created' if agent_id else 'config prepared'} successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating agent from persona: {str(e)}")
    finally:
        await service.close()


@router.get("/list", response_model=PersonaListResponse)
async def list_personas(
    active_only: bool = Query(True, description="Only return active personas"),
    thread_type: Optional[str] = Query(None, description="Filter by thread type")
):
    """
    List all available personas.

    Query Parameters:
    - active_only: Only return active personas (default: true)
    - thread_type: Filter by thread type (base, parallel, chained, fusion, big, zero_touch)

    Response:
    {
        "personas": [
            {
                "persona_id": "uuid",
                "name": "Developer",
                "version": "1.0",
                "description": "Software engineering specialist",
                "thread_type": "chained",
                "model_preference": "claude-sonnet-4-5",
                ...
            }
        ],
        "count": 8
    }
    """
    service = PersonaIntegrationService()

    try:
        personas = await service.list_personas(active_only=active_only)

        # Filter by thread type if specified
        if thread_type:
            personas = [p for p in personas if p.thread_type == thread_type]

        return PersonaListResponse(
            personas=[
                {
                    "persona_id": p.persona_id,
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "thread_type": p.thread_type,
                    "model_preference": p.model_preference,
                    "temperature": p.temperature,
                    "tools_access": p.tools_access,
                    "behavior_weights": p.behavior_weights,
                    "default_packs": p.default_packs
                }
                for p in personas
            ],
            count=len(personas)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing personas: {str(e)}")
    finally:
        await service.close()


@router.get("/{persona_id}", response_model=PersonaDetailResponse)
async def get_persona(persona_id: str):
    """
    Get detailed information about a persona.

    Path Parameters:
    - persona_id: Persona UUID

    Response:
    {
        "persona": {
            "persona_id": "uuid",
            "name": "Developer",
            "version": "1.0",
            ...
        },
        "enhancements": [
            {
                "enhancement_id": "uuid",
                "type": "tool",
                "name": "code-review-access",
                "priority": 5
            }
        ]
    }
    """
    service = PersonaIntegrationService()

    try:
        persona = await service.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

        # Fetch enhancements
        enhancements = await service.get_enhancements(persona_id)

        return PersonaDetailResponse(
            persona={
                "persona_id": persona.persona_id,
                "name": persona.name,
                "version": persona.version,
                "description": persona.description,
                "thread_type": persona.thread_type,
                "model_preference": persona.model_preference,
                "temperature": persona.temperature,
                "max_tokens": persona.max_tokens,
                "system_prompt_template": persona.system_prompt_template,
                "tools_access": persona.tools_access,
                "behavior_weights": persona.behavior_weights,
                "nats_subjects": persona.nats_subjects,
                "default_packs": persona.default_packs,
                "boosts": persona.boosts,
                "filters": persona.filters,
                "eval_gates": persona.eval_gates
            },
            enhancements=[
                {
                    "enhancement_id": e.enhancement_id,
                    "type": e.enhancement_type,
                    "name": e.enhancement_name,
                    "priority": e.priority,
                    "metadata": e.metadata
                }
                for e in enhancements
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting persona: {str(e)}")
    finally:
        await service.close()


@router.get("/enhancements/{persona_id}")
async def get_persona_enhancements(persona_id: str):
    """Get all enhancements for a persona."""
    service = PersonaIntegrationService()

    try:
        persona = await service.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

        enhancements = await service.get_enhancements(persona_id)

        return {
            "persona_id": persona_id,
            "persona_name": persona.name,
            "enhancements": [
                {
                    "enhancement_id": e.enhancement_id,
                    "type": e.enhancement_type,
                    "name": e.enhancement_name,
                    "value": e.enhancement_value,
                    "priority": e.priority,
                    "metadata": e.metadata
                }
                for e in enhancements
            ],
            "count": len(enhancements)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting enhancements: {str(e)}")
    finally:
        await service.close()


@router.post("/enhancements/{persona_id}")
async def add_persona_enhancement(
    persona_id: str,
    enhancement_type: str = Query(..., description="Enhancement type"),
    enhancement_name: str = Query(..., description="Enhancement name"),
    enhancement_value: Dict[str, Any] = None,
    priority: int = 0
):
    """Add an enhancement to a persona."""
    # This would require write access to Supabase
    # For now, return a not implemented response
    raise HTTPException(
        status_code=501,
        detail="Enhancement creation via API not yet implemented. Use Supabase directly."
    )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def persona_health():
    """Health check for persona integration."""
    service = PersonaIntegrationService()

    try:
        # Test Supabase connection
        personas = await service.list_personas(active_only=False)

        return {
            "status": "healthy",
            "supabase_connected": True,
            "total_personas": len(personas),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "supabase_connected": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        await service.close()


# ============================================================================
# Thread Type Info
# ============================================================================

@router.get("/thread-types")
async def get_thread_types():
    """Get available thread types with descriptions."""
    return {
        "thread_types": {
            "base": {
                "description": "Single agent, single task execution",
                "use_case": "Simple queries, direct actions",
                "coordination": "none"
            },
            "parallel": {
                "description": "Multiple independent agents executing simultaneously",
                "use_case": "Multi-source research, concurrent tasks",
                "coordination": "result_aggregation"
            },
            "chained": {
                "description": "Sequential agent handoff with context passing",
                "use_case": "Multi-step workflows, validation pipelines",
                "coordination": "sequential_handoff"
            },
            "fusion": {
                "description": "Multiple agents collaborating on single output",
                "use_case": "Complex analysis, consensus building",
                "coordination": "collaborative_merge"
            },
            "big": {
                "description": "Large context, multi-step planning with orchestration",
                "use_case": "Complex projects, architectural design",
                "coordination": "central_planner"
            },
            "zero_touch": {
                "description": "Fully automated execution without human input",
                "use_case": "Background tasks, scheduled operations",
                "coordination": "event_driven"
            }
        }
    }

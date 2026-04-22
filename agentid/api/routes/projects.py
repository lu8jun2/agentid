"""Project registration and participation routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from agentid.db.session import get_db
from agentid.models.project import Project, ProjectParticipation

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    owner_id: str


@router.post("", status_code=201)
async def create_project(body: CreateProjectRequest, db: AsyncSession = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        owner_id=body.owner_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.commit()
    return {"id": project.id, "name": project.name, "owner_id": project.owner_id}


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    parts = await db.execute(
        select(ProjectParticipation).where(ProjectParticipation.project_id == project_id)
    )
    return {
        "id": project.id, "name": project.name, "is_active": project.is_active,
        "participants": [{"agent_id": p.agent_id, "role": p.role} for p in parts.scalars()],
    }

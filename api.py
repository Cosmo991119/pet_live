"""
FastAPI entrypoint for the pet agent.

Run after installing FastAPI and Uvicorn:
    uvicorn api:app --reload
"""

import os
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from character_agent import (
    build_character_desktop_assets,
    create_character,
    generate_character_event,
    generate_character_sticker_pack,
    list_characters,
)
from image_styles import list_styles
from image_style_agent import transform_image_style
from notifier import notifier_from_env
from pet_db import (
    create_owner_for_telegram_chat,
    create_pet_memory,
    create_pet,
    delete_pet,
    delete_pet_relationship,
    get_pet,
    get_pet_stats,
    init_db,
    list_pet_memories,
    list_pet_relationships,
    list_pets,
    set_pet_relationship_muted,
    update_pet,
    upsert_pet_relationship,
)
from pet_event_service import process_pet_event
from pet_summary_agent import generate_and_store_summary
from pet_work_assistant import assist_with_text
from virtual_pet_service import (
    apply_virtual_pet_action,
    get_virtual_pet_snapshot,
    tick_virtual_pet,
)


app = FastAPI(title="Pet Agent API")
app.mount("/static", StaticFiles(directory="static"), name="static")


class PetEventRequest(BaseModel):
    pet_id: int
    behavior: str
    location_name: Optional[str] = None
    occurred_at: str
    confidence: float = Field(ge=0, le=1)


class PetCreateRequest(BaseModel):
    name: str
    owner_id: Optional[int] = None
    species: str = "cat"
    personality: str = "gentle"
    owner_call_name: str = "妈"
    pet_mode: str = "virtual"
    profile: Optional[dict[str, Any]] = None


class PetUpdateRequest(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    personality: Optional[str] = None
    owner_call_name: Optional[str] = None
    pet_mode: Optional[str] = None
    profile: Optional[dict[str, Any]] = None


class PetRelationshipRequest(BaseModel):
    labels: list[str] = Field(default_factory=list)
    note: str = ""
    muted: bool = False


class PetRelationshipMuteRequest(BaseModel):
    muted: bool


class PetMemoryRequest(BaseModel):
    memory_type: str
    content: str
    participant_pet_ids: list[int] = Field(default_factory=list)
    title: str = ""
    source: str = "manual"
    emotional_tone: str = ""
    importance: int = Field(default=3, ge=1, le=5)
    visibility: str = "home"
    metadata: Optional[dict[str, Any]] = None


class OwnerTelegramRequest(BaseModel):
    telegram_chat_id: str
    display_name: str = ""


class VirtualPetTickRequest(BaseModel):
    minutes: int = Field(default=10, ge=1, le=1440)


class VirtualPetActionRequest(BaseModel):
    action: str


class WorkAssistRequest(BaseModel):
    mode: str = "summarize"
    text: str


class ImageStyleResponse(BaseModel):
    image_url: str
    filename: str
    style_instruction: str
    style_mode: str


class ImageStyleOption(BaseModel):
    id: str
    label: str


class CharacterCreateRequest(BaseModel):
    image_url: str
    style_mode: str
    description: str = ""


class CharacterResponse(BaseModel):
    id: str
    image_url: str
    walking_reference_image_url: Optional[str] = None
    style_mode: str
    description: str
    created_at: str
    desktop_pet_manifest_url: Optional[str] = None
    desktop_pet_asset_dir: Optional[str] = None
    desktop_pet_avatar_url: Optional[str] = None


class CharacterEventRequest(BaseModel):
    prompt: str


class CharacterEventResponse(BaseModel):
    image_url: str
    filename: str
    character_id: str
    prompt: str


class CharacterStickerPackRequest(BaseModel):
    theme: str = ""


class CharacterStickerResponse(BaseModel):
    index: int
    image_url: str
    filename: str
    prompt: str


class CharacterStickerPackResponse(BaseModel):
    character_id: str
    theme: str
    stickers: list[CharacterStickerResponse]


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.get("/pets")
def get_pets(owner_id: Optional[int] = None) -> list[dict]:
    return list_pets(owner_id=owner_id)


@app.post("/owners/telegram")
def create_telegram_owner_endpoint(payload: OwnerTelegramRequest) -> dict:
    try:
        return create_owner_for_telegram_chat(
            telegram_chat_id=payload.telegram_chat_id,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/pets")
def create_pet_endpoint(payload: PetCreateRequest) -> dict:
    try:
        return create_pet(
            name=payload.name,
            owner_id=payload.owner_id,
            species=payload.species,
            personality=payload.personality,
            owner_call_name=payload.owner_call_name,
            pet_mode=payload.pet_mode,
            profile=payload.profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/pets/{pet_id}")
def update_pet_endpoint(
    pet_id: int,
    payload: PetUpdateRequest,
    owner_id: Optional[int] = None,
) -> dict:
    try:
        return update_pet(
            pet_id=pet_id,
            owner_id=owner_id,
            **payload.dict(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/pets/{pet_id}")
def delete_pet_endpoint(pet_id: int, owner_id: Optional[int] = None) -> dict:
    try:
        if owner_id is None:
            return delete_pet(pet_id)
        return delete_pet(pet_id, owner_id=owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/pet-relationships")
def list_pet_relationships_endpoint(
    pet_id: Optional[int] = None,
    from_pet_id: Optional[int] = None,
    to_pet_id: Optional[int] = None,
) -> list[dict]:
    return list_pet_relationships(
        pet_id=pet_id,
        from_pet_id=from_pet_id,
        to_pet_id=to_pet_id,
    )


@app.put("/pet-relationships/{from_pet_id}/{to_pet_id}")
def upsert_pet_relationship_endpoint(
    from_pet_id: int,
    to_pet_id: int,
    payload: PetRelationshipRequest,
) -> dict:
    try:
        return upsert_pet_relationship(
            from_pet_id=from_pet_id,
            to_pet_id=to_pet_id,
            labels=payload.labels,
            note=payload.note,
            muted=payload.muted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/pet-relationships/{from_pet_id}/{to_pet_id}/mute")
def mute_pet_relationship_endpoint(
    from_pet_id: int,
    to_pet_id: int,
    payload: PetRelationshipMuteRequest,
) -> dict:
    try:
        return set_pet_relationship_muted(from_pet_id, to_pet_id, payload.muted)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/pet-relationships/{from_pet_id}/{to_pet_id}")
def delete_pet_relationship_endpoint(from_pet_id: int, to_pet_id: int) -> dict:
    try:
        return delete_pet_relationship(from_pet_id, to_pet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/pet-memories")
def list_pet_memories_endpoint(
    pet_id: Optional[int] = None,
    memory_type: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    try:
        return list_pet_memories(
            pet_id=pet_id,
            memory_type=memory_type,
            visibility=visibility,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/pet-memories")
def create_pet_memory_endpoint(payload: PetMemoryRequest) -> dict:
    try:
        return create_pet_memory(
            memory_type=payload.memory_type,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            emotional_tone=payload.emotional_tone,
            importance=payload.importance,
            visibility=payload.visibility,
            participant_pet_ids=payload.participant_pet_ids,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/image-styles", response_model=list[ImageStyleOption])
def get_image_styles() -> list[dict]:
    return [{"id": style.id, "label": style.label} for style in list_styles()]


@app.get("/characters", response_model=list[CharacterResponse])
def get_characters() -> list[dict]:
    return list_characters()


@app.post("/characters", response_model=CharacterResponse)
def confirm_character(payload: CharacterCreateRequest) -> dict:
    try:
        return create_character(
            image_url=payload.image_url,
            style_mode=payload.style_mode,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/characters/{character_id}/desktop-assets", response_model=CharacterResponse)
def create_character_desktop_assets(
    character_id: str,
    animations: Optional[str] = None,
    provider: Optional[str] = None,
) -> dict:
    try:
        animation_names = None
        if animations:
            animation_names = [name.strip() for name in animations.split(",") if name.strip()]
        return build_character_desktop_assets(
            character_id,
            animation_names=animation_names,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/characters/{character_id}/events", response_model=CharacterEventResponse)
def create_character_event(character_id: str, payload: CharacterEventRequest) -> dict:
    try:
        return generate_character_event(character_id, payload.prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/characters/{character_id}/sticker-pack", response_model=CharacterStickerPackResponse)
def create_character_sticker_pack(character_id: str, payload: CharacterStickerPackRequest) -> dict:
    try:
        return generate_character_sticker_pack(character_id, theme=payload.theme)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/image-style", response_model=ImageStyleResponse)
async def create_styled_image(
    image: UploadFile = File(...),
    style: str = Form(...),
    style_mode: str = Form(default="figurine_3d"),
) -> dict:
    try:
        return transform_image_style(
            image_bytes=await image.read(),
            filename=image.filename or "input.png",
            content_type=image.content_type or "",
            style_instruction=style,
            style_mode=style_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/events")
def create_event(payload: PetEventRequest) -> dict:
    try:
        return process_pet_event(
            payload=payload.dict(),
            notifier=notifier_from_env(),
            use_llm=os.getenv("PET_AGENT_USE_LLM", "false").lower() == "true",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/pets/{pet_id}/summary")
def get_summary(pet_id: int, range: str = "week", end_date: Optional[str] = None) -> dict:
    try:
        return generate_and_store_summary(
            pet_id=pet_id,
            range_type=range,
            end_date=end_date,
            use_llm=os.getenv("PET_AGENT_USE_LLM", "false").lower() == "true",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/pets/{pet_id}/stats")
def get_stats(pet_id: int, range: str = "week", end_date: Optional[str] = None) -> dict:
    try:
        return get_pet_stats(
            pet_id=pet_id,
            range_type=range,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/virtual-pets/{pet_id}")
def get_virtual_pet(pet_id: int, owner_id: Optional[int] = None) -> dict:
    try:
        if owner_id is not None and get_pet(pet_id, owner_id=owner_id) is None:
            raise ValueError(f"pet_id {pet_id} does not exist")
        return get_virtual_pet_snapshot(pet_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/virtual-pets/{pet_id}/tick")
def tick_virtual_pet_endpoint(
    pet_id: int,
    payload: VirtualPetTickRequest,
    owner_id: Optional[int] = None,
) -> dict:
    try:
        if owner_id is not None and get_pet(pet_id, owner_id=owner_id) is None:
            raise ValueError(f"pet_id {pet_id} does not exist")
        return tick_virtual_pet(
            pet_id=pet_id,
            minutes=payload.minutes,
            notifier=notifier_from_env(),
            use_llm=os.getenv("PET_AGENT_USE_LLM", "false").lower() == "true",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/virtual-pets/{pet_id}/actions")
def virtual_pet_action_endpoint(
    pet_id: int,
    payload: VirtualPetActionRequest,
    owner_id: Optional[int] = None,
) -> dict:
    try:
        if owner_id is not None and get_pet(pet_id, owner_id=owner_id) is None:
            raise ValueError(f"pet_id {pet_id} does not exist")
        return apply_virtual_pet_action(
            pet_id=pet_id,
            action=payload.action,
            notifier=notifier_from_env(),
            use_llm=os.getenv("PET_AGENT_USE_LLM", "false").lower() == "true",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/assistant/text")
def assist_text_endpoint(payload: WorkAssistRequest) -> dict:
    try:
        return assist_with_text(mode=payload.mode, text=payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

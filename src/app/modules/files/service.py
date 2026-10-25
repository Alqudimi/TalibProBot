import hashlib
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.files.models import StoredAsset
from src.app.observability.logging import get_logger

logger = get_logger("files")


class FileStorageService:
    """Service managing stored assets metadata, hash validation, and retention."""

    @staticmethod
    async def register_asset(
        session: AsyncSession,
        owner_user_id: Optional[uuid.UUID],
        storage_key: str,
        media_type: str,
        byte_size: int,
        original_filename: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        asset_kind: str = "user_upload",
        sensitivity: str = "standard",
        storage_backend: str = "local",
    ) -> StoredAsset:
        asset = StoredAsset(
            id=uuid.uuid4(),
            owner_user_id=owner_user_id,
            storage_key=storage_key,
            original_filename=original_filename,
            media_type=media_type,
            byte_size=byte_size,
            sha256=sha256_hash,
            asset_kind=asset_kind,
            sensitivity=sensitivity,
            storage_backend=storage_backend,
        )
        session.add(asset)
        await session.flush()
        logger.info(f"Registered stored asset {asset.id} (key {storage_key}, {byte_size} bytes)")
        return asset

    @staticmethod
    async def get_asset(session: AsyncSession, asset_id: uuid.UUID) -> Optional[StoredAsset]:
        stmt = select(StoredAsset).where(StoredAsset.id == asset_id, StoredAsset.deleted_at.is_(None))
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

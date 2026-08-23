from __future__ import annotations

import asyncio
import base64
import io
import mimetypes
import os
import re
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import discord
from discord.ext import commands

import storage.photo_assets as photo_assets_db
import storage.photo_asset_blobs as photo_asset_blobs_db
import storage.photoroom_channels as photoroom_channels_db
import storage.dashboard_config as dashboard_config_db
from skylinebot.config.config import BotConfigClass
from skylinebot.console.logging import logger
from skylinebot.memory.cache import cache
from skylinebot.style import color
from skylinebot.style import urls as style_urls

PHOTO_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "photo"
ALLOWED_IMAGE_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}
PLAN_LIMITS: dict[str, int] = {
    "free": 10,
    "silver": 30,
    "golden": 60,
    "diamond": 100,
    "permanent": 300,
}
PLAN_NORMALIZE_MAP: dict[str, str] = {
    "free": "free",
    "basic": "free",
    "silver": "silver",
    "silver_guild_preminum": "silver",
    "premium_silver": "silver",
    "gold": "golden",
    "gole": "golden",
    "golden": "golden",
    "golden_guild_premium": "golden",
    "gole_guild_premium": "golden",
    "pro": "golden",
    "diamond": "diamond",
    "diamond_guild_premium": "diamond",
    "ultra": "diamond",
    "permanent": "permanent",
    "lifetime": "permanent",
    "forever": "permanent",
    "permanent_guild_premium": "permanent",
    "lifetime_guild_premium": "permanent",
}
DEFAULT_PHOTOROOM_STORAGE_CHANNEL_ID = 1505283357632893104
OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY = "ownerbot_upload_channels_v1"
OWNERBOT_PHOTOROOM_UPLOAD_TARGET_KEYS: tuple[str, ...] = (
    "photo_asset",
    "photoroom_asset",
    "photo",
    "photoroom",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_plan_tier(raw_value: Any) -> str:
    normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
    return PLAN_NORMALIZE_MAP.get(normalized, "free")


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    filename = str(getattr(attachment, "filename", "") or "").strip().lower()
    if filename.endswith(tuple(ALLOWED_IMAGE_EXTENSIONS)):
        return True
    content_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
    return bool(content_type.startswith("image/"))


def _slugify_photo_name(raw_value: str, *, fallback: str = "photo") -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        raw = fallback
    raw = raw.replace("\\", " ").replace("/", " ")
    raw = re.sub(r"\s+", "-", raw)
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    cleaned = cleaned.lower()
    if not cleaned:
        cleaned = fallback
    return cleaned[:80]


def _filename_stem(filename: str) -> str:
    stem = str(Path(str(filename or "").strip()).stem or "").strip()
    return stem or "photo"


def _file_extension_from_attachment(attachment: discord.Attachment) -> str:
    ext = str(Path(str(getattr(attachment, "filename", "") or "").strip()).suffix or "").lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return ext
    content_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
    guessed_ext = mimetypes.guess_extension(content_type.split(";", 1)[0] if content_type else "") or ""
    guessed_ext = str(guessed_ext or "").lower()
    if guessed_ext in ALLOWED_IMAGE_EXTENSIONS:
        return guessed_ext
    return ".png"


class PhotoRenameModal(discord.ui.Modal):
    def __init__(self, cog: "PhotoRoom", asset_id: int, current_slug: str):
        super().__init__(title="Edit Photo Name", timeout=300)
        self.cog = cog
        self.asset_id = int(asset_id)
        self.new_name = discord.ui.TextInput(
            label="New Photo Name",
            placeholder="Enter new name",
            default=str(current_slug or "")[:80],
            max_length=80,
            required=True,
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.rename_asset_from_modal(
            interaction=interaction,
            asset_id=self.asset_id,
            raw_name=str(self.new_name.value or ""),
        )


class PhotoAssetManageView(discord.ui.View):
    def __init__(self, cog: "PhotoRoom"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Edit Name", style=discord.ButtonStyle.secondary, custom_id="photoroom:rename")
    async def rename_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        asset = await self.cog.get_asset_by_control_message(interaction)
        if not asset:
            return await self.cog.safe_interaction_reply(
                interaction,
                "Photo entry not found or already removed.",
                ephemeral=True,
            )
        if not await self.cog.can_manage_asset(interaction, asset):
            return await self.cog.safe_interaction_reply(
                interaction,
                "Only users who can send messages in PhotoRoom can manage links.",
                ephemeral=True,
            )
        await interaction.response.send_modal(
            PhotoRenameModal(
                cog=self.cog,
                asset_id=int(asset.get("id") or 0),
                current_slug=str(asset.get("slug") or ""),
            )
        )

    @discord.ui.button(label="Edit Image", style=discord.ButtonStyle.secondary, custom_id="photoroom:replace")
    async def replace_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        asset = await self.cog.get_asset_by_control_message(interaction)
        if not asset:
            return await self.cog.safe_interaction_reply(
                interaction,
                "Photo entry not found or already removed.",
                ephemeral=True,
            )
        if not await self.cog.can_manage_asset(interaction, asset):
            return await self.cog.safe_interaction_reply(
                interaction,
                "Only users who can send messages in PhotoRoom can manage links.",
                ephemeral=True,
            )
        await self.cog.replace_asset_from_button(interaction=interaction, asset=asset)

    @discord.ui.button(label="Delete Photo", style=discord.ButtonStyle.danger, custom_id="photoroom:delete")
    async def delete_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        asset = await self.cog.get_asset_by_control_message(interaction)
        if not asset:
            return await self.cog.safe_interaction_reply(
                interaction,
                "Photo entry not found or already removed.",
                ephemeral=True,
            )
        if not await self.cog.can_manage_asset(interaction, asset):
            return await self.cog.safe_interaction_reply(
                interaction,
                "Only users who can send messages in PhotoRoom can manage links.",
                ephemeral=True,
            )
        deleted = await self.cog.delete_asset_record(
            asset=asset,
            deleted_by=getattr(getattr(interaction, "user", None), "id", 0),
            mark_control_message=False,
        )
        if not deleted:
            return await self.cog.safe_interaction_reply(
                interaction,
                "Failed to delete this photo.",
                ephemeral=True,
            )

        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=self.cog._build_deleted_embed(asset),
                view=None,
                content=None,
            )
            return
        await interaction.response.edit_message(
            embed=self.cog._build_deleted_embed(asset),
            view=None,
            content=None,
        )


class PhotoRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._config = BotConfigClass()
        self._refresh_existing_embeds_task: asyncio.Task | None = None
        self._legacy_local_migration_task: asyncio.Task | None = None
        self._storage_backend_warning_logged = False
        try:
            self.bot.add_view(PhotoAssetManageView(self))
        except Exception:
            pass

    async def cog_load(self) -> None:
        if self._legacy_local_migration_task is None or self._legacy_local_migration_task.done():
            self._legacy_local_migration_task = asyncio.create_task(
                self._migrate_legacy_local_assets_to_mongodb()
            )
        if self._refresh_existing_embeds_task is None or self._refresh_existing_embeds_task.done():
            self._refresh_existing_embeds_task = asyncio.create_task(self._refresh_existing_control_messages())

    def cog_unload(self) -> None:
        if self._legacy_local_migration_task and not self._legacy_local_migration_task.done():
            self._legacy_local_migration_task.cancel()
        if self._refresh_existing_embeds_task and not self._refresh_existing_embeds_task.done():
            self._refresh_existing_embeds_task.cancel()

    async def _refresh_existing_control_messages(self) -> None:
        try:
            await self.bot.wait_until_ready()
            await asyncio.sleep(2)
            assets = await photo_assets_db.get_all()
        except Exception:
            return

        refreshed = 0
        for asset in list(assets or []):
            if not isinstance(asset, dict):
                continue
            try:
                await self.refresh_asset_message(asset)
                refreshed += 1
            except Exception:
                continue
            if refreshed % 10 == 0:
                await asyncio.sleep(0.25)
        if refreshed > 0:
            logger.info(f"photoroom embed backfill refreshed | count={refreshed}")

    async def _migrate_legacy_local_assets_to_mongodb(self) -> None:
        try:
            await self.bot.wait_until_ready()
            await asyncio.sleep(1)
            assets = await photo_assets_db.get_all()
        except Exception:
            return

        migrated = 0
        skipped = 0
        failed = 0
        for asset in list(assets or []):
            if not isinstance(asset, dict):
                continue

            backend = str(asset.get("storage_backend") or "").strip().lower()
            if backend not in {"", "local"}:
                continue
            asset_id = int(asset.get("id") or 0)
            guild_id = int(asset.get("guild_id") or 0)
            stored_filename = str(asset.get("stored_filename") or "").strip()
            if asset_id <= 0 or guild_id <= 0 or not stored_filename:
                skipped += 1
                continue

            file_path = self._asset_file_path(guild_id, stored_filename)
            if not file_path.exists() or not file_path.is_file():
                skipped += 1
                continue

            try:
                payload = await asyncio.to_thread(file_path.read_bytes)
            except Exception:
                failed += 1
                continue
            if not payload:
                failed += 1
                continue

            mime_type = str(asset.get("mime_type") or "").strip().lower()
            if not mime_type:
                guessed, _ = mimetypes.guess_type(str(file_path))
                mime_type = str(guessed or "application/octet-stream")

            blob_ok = await self._upsert_mongodb_blob_for_asset(
                asset_id=asset_id,
                guild_id=guild_id,
                payload=payload,
                mime_type=mime_type,
                file_size=len(payload),
            )
            if not blob_ok:
                failed += 1
                continue

            updated = await photo_assets_db.update(
                id=asset_id,
                storage_backend="mongodb",
                external_url="",
                external_id="",
                storage_channel_id=0,
                storage_message_id=0,
                storage_guild_id=0,
                mime_type=str(mime_type or "application/octet-stream")[:120],
                file_size=len(payload),
                updated_at=_utc_now(),
            )
            if not updated:
                failed += 1
                continue

            try:
                file_path.unlink()
            except Exception:
                pass

            migrated += 1
            if migrated % 20 == 0:
                await asyncio.sleep(0)

        if migrated or failed:
            logger.info(
                "photoroom local->mongodb migration finished | "
                f"migrated={migrated} skipped={skipped} failed={failed}"
            )

    def _base_url(self) -> str:
        configured = str(getattr(self._config, "DASHBOARD_BASE_URL", "") or "").strip()
        if not configured:
            configured = str(os.getenv("DASHBOARD_BASE_URL", "") or "").strip()
        if not configured:
            configured = "https://skylinebot.xyz"
        if "://" not in configured:
            configured = f"https://{configured}"
        return configured.rstrip("/")

    def _guild_plan_tier(self, guild_id: int) -> str:
        guild_data = cache.guilds.get(str(int(guild_id)), {}) or {}
        return _normalize_plan_tier(guild_data.get("subscription", "free"))

    def _plan_limit(self, guild_id: int) -> int:
        tier = self._guild_plan_tier(guild_id)
        return int(PLAN_LIMITS.get(tier, PLAN_LIMITS["free"]))

    def _plan_display(self, guild_id: int) -> str:
        tier = self._guild_plan_tier(guild_id)
        return tier.capitalize() if tier else "Free"

    def _scope_guild_id(self, guild_id: int) -> int:
        return int(style_urls.photo_scope_guild_id(guild_id))

    def _photo_link(self, guild_id: int, slug: str) -> str:
        return style_urls.photo_url(guild_id, slug, base_url=self._base_url())

    def _asset_file_path(self, guild_id: int, stored_filename: str) -> Path:
        safe_name = Path(str(stored_filename or "")).name
        return PHOTO_UPLOAD_ROOT / str(int(guild_id)) / safe_name

    def _storage_backend(self) -> str:
        raw = str(os.getenv("PHOTOROOM_STORAGE_BACKEND", "mongodb") or "").strip().lower()
        if raw not in {"", "mongo", "mongodb", "db", "database"} and not self._storage_backend_warning_logged:
            logger.warning(
                "photoroom storage backend overridden to mongodb | "
                f"configured_backend={raw}"
            )
            self._storage_backend_warning_logged = True
        return "mongodb"

    def _storage_backend_label(self, backend: str) -> str:
        key = str(backend or "").strip().lower()
        if key == "discord_channel":
            return "Discord Storage Room"
        if key == "mongodb":
            return "MongoDB"
        if key == "google_drive":
            return "Google Drive"
        return "Local Server"

    def _env_bool(self, env_name: str, default: bool = False) -> bool:
        raw = os.getenv(env_name)
        if raw is None:
            return bool(default)
        text = str(raw).strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
        return bool(default)

    def _storage_channel_id(self) -> int:
        raw = str(
            os.getenv(
                "PHOTOROOM_STORAGE_CHANNEL_ID",
                str(DEFAULT_PHOTOROOM_STORAGE_CHANNEL_ID),
            )
            or ""
        ).strip()
        return int(raw) if raw.isdigit() else 0

    def _gdrive_folder_id(self) -> str:
        return str(os.getenv("PHOTOROOM_GDRIVE_FOLDER_ID", "") or "").strip()

    def _gdrive_share_public(self) -> bool:
        return self._env_bool("PHOTOROOM_GDRIVE_SHARE_PUBLIC", True)

    def _gdrive_service_account_payload(self) -> dict[str, Any] | None:
        raw_inline = str(os.getenv("PHOTOROOM_GDRIVE_SERVICE_ACCOUNT_JSON", "") or "").strip()
        raw_file = str(os.getenv("PHOTOROOM_GDRIVE_SERVICE_ACCOUNT_FILE", "") or "").strip()
        raw_base64 = str(os.getenv("PHOTOROOM_GDRIVE_SERVICE_ACCOUNT_JSON_BASE64", "") or "").strip()

        def _parse_json(text: str) -> dict[str, Any] | None:
            try:
                decoded = json.loads(text)
            except Exception:
                return None
            return decoded if isinstance(decoded, dict) else None

        if raw_file:
            try:
                file_path = Path(raw_file).expanduser()
                if file_path.exists() and file_path.is_file():
                    payload = _parse_json(file_path.read_text(encoding="utf-8"))
                    if payload:
                        return payload
            except Exception:
                pass

        if raw_inline:
            payload = _parse_json(raw_inline)
            if payload:
                return payload
            try:
                file_path = Path(raw_inline).expanduser()
                if file_path.exists() and file_path.is_file():
                    payload = _parse_json(file_path.read_text(encoding="utf-8"))
                    if payload:
                        return payload
            except Exception:
                pass

        if raw_base64:
            try:
                decoded_text = base64.b64decode(raw_base64).decode("utf-8", errors="ignore")
                payload = _parse_json(decoded_text)
                if payload:
                    return payload
            except Exception:
                pass
        return None

    async def _ownerbot_mapped_storage_channel_id(self) -> int:
        try:
            row = await dashboard_config_db.get(
                config_key=OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY
            )
        except Exception:
            return 0
        if not isinstance(row, dict):
            return 0
        raw_value = str(row.get("config_value") or "").strip()
        if not raw_value:
            return 0
        try:
            decoded = json.loads(raw_value)
        except Exception:
            return 0
        if not isinstance(decoded, dict):
            return 0
        channels = decoded.get("channels")
        if not isinstance(channels, dict):
            return 0
        for target_key in OWNERBOT_PHOTOROOM_UPLOAD_TARGET_KEYS:
            channel_id_text = str(channels.get(target_key) or "").strip()
            if channel_id_text.isdigit():
                return int(channel_id_text)
        return 0

    async def _resolve_storage_channel(self) -> discord.TextChannel | discord.Thread | None:
        if self._storage_backend() != "discord_channel":
            return None
        channel_ids: list[int] = []
        mapped_channel_id = await self._ownerbot_mapped_storage_channel_id()
        if mapped_channel_id > 0:
            channel_ids.append(mapped_channel_id)
        env_channel_id = self._storage_channel_id()
        if env_channel_id > 0 and env_channel_id not in channel_ids:
            channel_ids.append(env_channel_id)
        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                for guild in getattr(self.bot, "guilds", []):
                    channel = guild.get_channel(channel_id)
                    if channel is not None:
                        break
            if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue

            guild = getattr(channel, "guild", None)
            me = getattr(guild, "me", None) if guild is not None else None
            if me is None:
                continue
            permissions = channel.permissions_for(me)
            if not (permissions.view_channel and permissions.send_messages and permissions.attach_files):
                continue
            return channel
        return None

    async def _delete_discord_storage_message(self, *, channel_id: int, message_id: int) -> None:
        if int(channel_id or 0) <= 0 or int(message_id or 0) <= 0:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            return
        try:
            message = await channel.fetch_message(int(message_id))
            await message.delete()
        except Exception:
            return

    async def _save_attachment_to_discord_channel(
        self,
        *,
        guild_id: int,
        attachment: discord.Attachment,
        storage_channel: discord.TextChannel | discord.Thread,
    ) -> dict[str, Any] | None:
        try:
            try:
                discord_file = await attachment.to_file(use_cached=True)
            except TypeError:
                discord_file = await attachment.to_file()
            sent = await storage_channel.send(
                content=f"[photoroom-storage] guild={int(guild_id)} file={attachment.filename}",
                file=discord_file,
            )
        except Exception as error:
            logger.warning(
                "photoroom discord storage upload failed | "
                f"guild={int(guild_id)} channel={int(getattr(storage_channel, 'id', 0) or 0)} "
                f"file={attachment.filename} error={error}"
            )
            return None

        uploaded = (list(getattr(sent, "attachments", []) or []) or [None])[0]
        if uploaded is None:
            return None

        external_url = str(getattr(uploaded, "url", "") or "").strip()
        if not external_url:
            return None
        mime_type = str(getattr(uploaded, "content_type", "") or "").strip().lower()
        if not mime_type:
            mime_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
        if not mime_type:
            guessed = mimetypes.guess_type(str(getattr(uploaded, "filename", "") or ""))[0]
            mime_type = str(guessed or "application/octet-stream")

        return {
            "external_url": external_url,
            "storage_channel_id": int(getattr(storage_channel, "id", 0) or 0),
            "storage_message_id": int(getattr(sent, "id", 0) or 0),
            "storage_guild_id": int(getattr(getattr(storage_channel, "guild", None), "id", 0) or 0),
            "mime_type": mime_type[:120],
            "file_size": int(getattr(uploaded, "size", 0) or 0),
            "storage_backend": "discord_channel",
        }

    async def _save_attachment_to_google_drive(
        self,
        *,
        guild_id: int,
        attachment: discord.Attachment,
    ) -> dict[str, Any] | None:
        folder_id = self._gdrive_folder_id()
        credentials_payload = self._gdrive_service_account_payload()
        if not folder_id or not credentials_payload:
            logger.warning(
                "photoroom google drive config missing | "
                f"guild={int(guild_id)} folder_id_set={bool(folder_id)} credentials_set={bool(credentials_payload)}"
            )
            return None

        try:
            data = await attachment.read()
        except Exception as error:
            logger.warning(
                "photoroom google drive read failed | "
                f"guild={int(guild_id)} file={attachment.filename} error={error}"
            )
            return None
        if not data:
            return None

        extension = _file_extension_from_attachment(attachment)
        stored_filename = f"gdrive-{uuid.uuid4().hex}{extension}"
        mime_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
        if not mime_type:
            guessed = mimetypes.guess_type(stored_filename)[0]
            mime_type = str(guessed or "application/octet-stream")

        def _upload_sync() -> dict[str, Any] | None:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaIoBaseUpload
            except Exception as import_error:
                logger.warning(f"photoroom google drive import failed: {import_error}")
                return None

            try:
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_payload,
                    scopes=["https://www.googleapis.com/auth/drive.file"],
                )
                drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
                media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=False)
                metadata: dict[str, Any] = {"name": stored_filename}
                if folder_id:
                    metadata["parents"] = [folder_id]
                created = (
                    drive_service.files()
                    .create(
                        body=metadata,
                        media_body=media,
                        fields="id,mimeType,size",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                file_id = str((created or {}).get("id") or "").strip()
                if not file_id:
                    return None
                if self._gdrive_share_public():
                    try:
                        (
                            drive_service.permissions()
                            .create(
                                fileId=file_id,
                                body={"role": "reader", "type": "anyone"},
                                supportsAllDrives=True,
                                fields="id",
                            )
                            .execute()
                        )
                    except Exception as permission_error:
                        logger.warning(
                            "photoroom google drive permission set failed | "
                            f"file_id={file_id} error={permission_error}"
                        )
                file_size = int((created or {}).get("size") or len(data))
                external_url = (
                    f"https://drive.google.com/uc?export=view&id={file_id}"
                    if self._gdrive_share_public()
                    else f"https://drive.google.com/file/d/{file_id}/view"
                )
                return {
                    "external_url": external_url,
                    "external_id": file_id,
                    "storage_backend": "google_drive",
                    "mime_type": str((created or {}).get("mimeType") or mime_type or "application/octet-stream"),
                    "file_size": file_size,
                    "stored_filename": stored_filename,
                }
            except Exception as upload_error:
                logger.warning(
                    "photoroom google drive upload failed | "
                    f"guild={int(guild_id)} file={attachment.filename} error={upload_error}"
                )
                return None

        return await asyncio.to_thread(_upload_sync)

    async def _delete_google_drive_file(self, *, file_id: str) -> None:
        safe_file_id = str(file_id or "").strip()
        if not safe_file_id:
            return
        credentials_payload = self._gdrive_service_account_payload()
        if not credentials_payload:
            return

        def _delete_sync() -> None:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from googleapiclient.errors import HttpError
            except Exception:
                return

            try:
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_payload,
                    scopes=["https://www.googleapis.com/auth/drive.file"],
                )
                drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
                (
                    drive_service.files()
                    .delete(fileId=safe_file_id, supportsAllDrives=True)
                    .execute()
                )
            except HttpError as http_error:
                # 404 means already deleted/not found, safe to ignore.
                status_code = int(getattr(getattr(http_error, "resp", None), "status", 0) or 0)
                if status_code != 404:
                    logger.warning(
                        "photoroom google drive delete failed | "
                        f"file_id={safe_file_id} status={status_code}"
                    )
            except Exception as delete_error:
                logger.warning(
                    "photoroom google drive delete failed | "
                    f"file_id={safe_file_id} error={delete_error}"
                )

        await asyncio.to_thread(_delete_sync)

    async def safe_interaction_reply(self, interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
        if interaction.response.is_done():
            await interaction.followup.send(content=content, ephemeral=ephemeral)
            return
        await interaction.response.send_message(content=content, ephemeral=ephemeral)

    async def _safe_ctx_defer(self, ctx: commands.Context, *, ephemeral: bool = False) -> bool:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return False
        if interaction.response.is_done():
            return True
        try:
            await ctx.defer(ephemeral=ephemeral)
            return True
        except (discord.NotFound, discord.InteractionResponded):
            return False
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return False
            raise

    async def _safe_ctx_send(self, ctx: commands.Context, content: str | None = None, **kwargs):
        try:
            if content is not None:
                return await ctx.send(content, **kwargs)
            return await ctx.send(**kwargs)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except discord.HTTPException as send_error:
            if getattr(send_error, "code", None) != 10062:
                raise

        channel = getattr(ctx, "channel", None)
        if channel is None:
            return None
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("ephemeral", None)
        if content is not None:
            return await channel.send(content, **fallback_kwargs)
        return await channel.send(**fallback_kwargs)

    async def _configured_room_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        row = await photoroom_channels_db.get(guild_id=int(guild.id))
        if not row:
            return None
        channel_id = int(row.get("channel_id") or 0)
        channel = guild.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return None
        return channel

    def _member_can_send_in_room(self, member: discord.Member, room: discord.TextChannel) -> bool:
        permissions = room.permissions_for(member)
        return bool(permissions.view_channel and permissions.send_messages)

    async def _can_actor_use_photoroom(
        self,
        *,
        guild: discord.Guild,
        actor: discord.Member | discord.User | None,
    ) -> tuple[discord.TextChannel | None, str | None]:
        room = await self._configured_room_channel(guild)
        if room is None:
            return None, "PhotoRoom is not configured yet. Use `/setup photoroom` first."
        if actor is None:
            return None, "Unable to resolve user."
        member = actor if isinstance(actor, discord.Member) else guild.get_member(int(getattr(actor, "id", 0) or 0))
        if member is None:
            return None, "Member was not found in this guild."
        if not self._member_can_send_in_room(member, room):
            return None, f"Only users who can send messages in {room.mention} can use this."
        return room, None

    async def _upsert_photoroom_channel(self, *, guild_id: int, channel_id: int, updated_by: int) -> dict[str, Any] | None:
        existing = await photoroom_channels_db.get(guild_id=guild_id)
        now = _utc_now()
        if existing and existing.get("id"):
            return await photoroom_channels_db.update(
                id=int(existing["id"]),
                guild_id=guild_id,
                channel_id=channel_id,
                updated_by=int(updated_by),
                updated_at=now,
            )
        return await photoroom_channels_db.insert(
            guild_id=guild_id,
            channel_id=channel_id,
            updated_by=int(updated_by),
            created_at=now,
            updated_at=now,
        )

    async def _auto_create_photoroom_channel(
        self,
        *,
        guild: discord.Guild,
        requester_channel: discord.abc.GuildChannel | None = None,
    ) -> tuple[discord.TextChannel | None, str | None]:
        base_name_raw = str(os.getenv("PHOTO_ROOM_CHANNEL_NAME", "photo-room") or "photo-room").strip().lower()
        base_name = re.sub(r"[^a-z0-9-_]", "-", base_name_raw)
        base_name = re.sub(r"-{2,}", "-", base_name).strip("-") or "photo-room"

        for channel in guild.text_channels:
            if str(channel.name or "").strip().lower() == base_name:
                return channel, None

        me = guild.me
        if me is None:
            return None, "Bot is not ready to auto-create channel."

        guild_permissions = me.guild_permissions
        if not guild_permissions.manage_channels:
            return None, "Bot needs `Manage Channels` permission to auto-create room."

        target_category = requester_channel.category if isinstance(requester_channel, discord.TextChannel) else None
        try:
            created = await guild.create_text_channel(
                name=base_name[:95],
                category=target_category,
                reason="Auto create by /setup photoroom"[:512],
            )
            return created, None
        except Exception as error:
            return None, f"Auto-create room failed: {error}"

    async def _resolve_unique_slug(self, *, scope_guild_id: int, preferred: str, exclude_id: int = 0) -> str:
        base = _slugify_photo_name(preferred, fallback="photo")
        candidate = base
        suffix = 2
        while True:
            existing = await photo_assets_db.get(scope_guild_id=scope_guild_id, slug=candidate)
            if not existing:
                return candidate
            if exclude_id > 0 and int(existing.get("id") or 0) == int(exclude_id):
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1
            if suffix > 9999:
                return f"{base}-{uuid.uuid4().hex[:6]}"

    async def _store_attachment_by_backend(
        self,
        *,
        guild_id: int,
        attachment: discord.Attachment,
    ) -> dict[str, Any] | None:
        try:
            mongodb_payload = await attachment.read()
        except Exception as read_error:
            logger.warning(
                "photoroom mongodb read failed | "
                f"guild={guild_id} file={attachment.filename} error={read_error}"
            )
            return None
        if not mongodb_payload:
            return None

        extension = _file_extension_from_attachment(attachment)
        stored_filename = f"mongo-{uuid.uuid4().hex}{extension}"
        file_size = len(mongodb_payload)
        mime_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
        if not mime_type:
            guessed = mimetypes.guess_type(stored_filename)[0]
            mime_type = str(guessed or "application/octet-stream")

        return {
            "stored_filename": stored_filename,
            "file_size": int(file_size),
            "mime_type": str(mime_type or "application/octet-stream").strip().lower()[:120],
            "external_url": "",
            "external_id": "",
            "storage_backend": "mongodb",
            "storage_channel_id": 0,
            "storage_message_id": 0,
            "storage_guild_id": 0,
            "mongodb_payload": mongodb_payload,
        }

    def _asset_cache_token(self, asset: dict[str, Any]) -> str:
        version_source = asset.get("updated_at") or asset.get("created_at") or asset.get("id") or uuid.uuid4().hex
        if isinstance(version_source, datetime):
            token = str(int(version_source.timestamp() * 1000))
        else:
            token = str(version_source or "").strip()
        cleaned = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_"})
        return cleaned or uuid.uuid4().hex[:12]

    def _asset_image_url(self, *, guild_id: int, asset: dict[str, Any]) -> str:
        slug = str(asset.get("slug") or "").strip()
        base_url = self._photo_link(guild_id, slug)
        cache_token = quote(self._asset_cache_token(asset), safe="-_")
        return f"{base_url}?v={cache_token}"

    async def _cleanup_single_asset_storage(
        self,
        row: dict[str, Any],
        *,
        skip_mongodb_blob: bool = False,
    ) -> None:
        if not isinstance(row, dict):
            return
        asset_id = int(row.get("id") or 0)
        backend = str(row.get("storage_backend") or "").strip().lower() or "local"
        storage_message_id = int(row.get("storage_message_id") or 0)
        storage_channel_id = int(row.get("storage_channel_id") or 0)

        if backend == "discord_channel" and storage_channel_id > 0 and storage_message_id > 0:
            await self._delete_discord_storage_message(channel_id=storage_channel_id, message_id=storage_message_id)
        elif backend == "mongodb" and asset_id > 0 and not skip_mongodb_blob:
            try:
                await photo_asset_blobs_db.delete(asset_id=asset_id)
            except Exception:
                pass
        elif backend == "google_drive":
            file_id = str(row.get("external_id") or "").strip()
            if file_id:
                await self._delete_google_drive_file(file_id=file_id)

        if backend == "local":
            try:
                file_path = self._asset_file_path(int(row.get("guild_id") or 0), str(row.get("stored_filename") or ""))
                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
            except Exception:
                pass

    def _build_asset_embed(self, *, guild_id: int, asset: dict[str, Any], used: int, limit: int) -> discord.Embed:
        slug = str(asset.get("slug") or "").strip()
        url = self._photo_link(guild_id, slug)
        image_url = self._asset_image_url(guild_id=guild_id, asset=asset)
        embed = discord.Embed(
            title="Photo URL Created",
            description=f"`{slug}`",
            color=color.green,
        )
        embed.add_field(name="Link", value=f"<{url}>", inline=False)
        embed.add_field(name="Plan Usage", value=f"{used}/{limit}", inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text="Buttons: Edit Name / Edit Image / Delete Photo")
        return embed

    def _build_deleted_embed(self, asset: dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title="Photo Deleted",
            description=f"Name: `{str(asset.get('slug') or '-')}`",
            color=color.red,
        )
        embed.set_footer(text="This link is no longer available.")
        return embed

    async def get_asset_by_control_message(self, interaction: discord.Interaction) -> dict[str, Any] | None:
        if not interaction.guild or not interaction.message:
            return None
        asset = await photo_assets_db.get(control_message_id=int(interaction.message.id))
        if not asset:
            return None
        if int(asset.get("guild_id") or 0) != int(interaction.guild.id):
            return None
        return asset

    async def _edit_control_message_deleted(self, asset: dict[str, Any]) -> None:
        guild_id = int(asset.get("guild_id") or 0)
        channel_id = int(asset.get("upload_channel_id") or 0)
        message_id = int(asset.get("control_message_id") or 0)
        if guild_id <= 0 or channel_id <= 0 or message_id <= 0:
            return
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        channel = guild.get_channel(channel_id)
        if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=self._build_deleted_embed(asset), view=None, content=None)
        except Exception:
            return

    async def refresh_asset_message(self, asset: dict[str, Any]) -> None:
        guild_id = int(asset.get("guild_id") or 0)
        channel_id = int(asset.get("upload_channel_id") or 0)
        message_id = int(asset.get("control_message_id") or 0)
        if guild_id <= 0 or channel_id <= 0 or message_id <= 0:
            return
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        channel = guild.get_channel(channel_id)
        if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            return
        used = await photo_assets_db.count(guild_id=guild_id)
        limit = self._plan_limit(guild_id)
        embed = self._build_asset_embed(guild_id=guild_id, asset=asset, used=used, limit=limit)
        try:
            await message.edit(embed=embed, view=PhotoAssetManageView(self))
        except Exception:
            return

    async def can_manage_asset(self, interaction: discord.Interaction, asset: dict[str, Any]) -> bool:
        if not interaction.guild:
            return False
        if int(asset.get("guild_id") or 0) != int(interaction.guild.id):
            return False
        room = await self._configured_room_channel(interaction.guild)
        if room is None:
            return False
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            member = interaction.guild.get_member(int(getattr(interaction.user, "id", 0) or 0))
        if member is None:
            return False
        return self._member_can_send_in_room(member, room)

    async def rename_asset_from_modal(self, *, interaction: discord.Interaction, asset_id: int, raw_name: str) -> None:
        asset = await photo_assets_db.get(id=int(asset_id))
        if not asset:
            return await self.safe_interaction_reply(
                interaction,
                "Photo entry not found or already removed.",
                ephemeral=True,
            )
        if not await self.can_manage_asset(interaction, asset):
            return await self.safe_interaction_reply(
                interaction,
                "Only users who can send messages in PhotoRoom can manage links.",
                ephemeral=True,
            )
        desired_slug = _slugify_photo_name(raw_name, fallback="photo")
        if desired_slug == str(asset.get("slug") or "").strip():
            return await self.safe_interaction_reply(
                interaction,
                "Photo name is unchanged.",
                ephemeral=True,
            )

        duplicate_asset = await self._find_scope_asset_by_slug(
            guild_id=int(asset.get("guild_id") or 0),
            slug_value=desired_slug,
            exclude_id=int(asset.get("id") or 0),
        )
        if duplicate_asset:
            duplicate_url = self._photo_link(
                int(duplicate_asset.get("guild_id") or asset.get("guild_id") or 0),
                desired_slug,
            )
            return await self.safe_interaction_reply(
                interaction,
                f"Photo URL `{desired_slug}` already exists.\n{duplicate_url}",
                ephemeral=True,
            )

        updated = await photo_assets_db.update(
            id=int(asset["id"]),
            slug=desired_slug,
            display_name=str(raw_name or "").strip()[:120],
            updated_at=_utc_now(),
        )
        if not updated:
            return await self.safe_interaction_reply(
                interaction,
                "Failed to rename this photo.",
                ephemeral=True,
            )
        await self.refresh_asset_message(updated)
        new_url = self._photo_link(int(updated.get("guild_id") or 0), str(updated.get("slug") or ""))
        await self.safe_interaction_reply(
            interaction,
            f"Updated name to `{updated.get('slug')}`\n{new_url}",
            ephemeral=True,
        )

    async def _upsert_mongodb_blob_for_asset(
        self,
        *,
        asset_id: int,
        guild_id: int,
        payload: bytes,
        mime_type: str,
        file_size: int,
    ) -> bool:
        if asset_id <= 0 or not payload:
            return False
        existing = await photo_asset_blobs_db.get(asset_id=int(asset_id))
        now = _utc_now()
        if existing and existing.get("id"):
            updated = await photo_asset_blobs_db.update(
                id=int(existing["id"]),
                asset_id=int(asset_id),
                guild_id=int(guild_id),
                payload=payload,
                mime_type=str(mime_type or "application/octet-stream")[:120],
                file_size=int(file_size),
                updated_at=now,
            )
            return bool(updated)
        inserted = await photo_asset_blobs_db.insert(
            asset_id=int(asset_id),
            guild_id=int(guild_id),
            payload=payload,
            mime_type=str(mime_type or "application/octet-stream")[:120],
            file_size=int(file_size),
            created_at=now,
            updated_at=now,
        )
        return bool(inserted)

    async def _replace_asset_attachment(
        self,
        *,
        asset: dict[str, Any],
        attachment: discord.Attachment,
        replaced_by: int = 0,
        source_message_id: int = 0,
    ) -> dict[str, Any] | None:
        if not isinstance(asset, dict):
            return None
        asset_id = int(asset.get("id") or 0)
        guild_id = int(asset.get("guild_id") or 0)
        if asset_id <= 0 or guild_id <= 0:
            return None

        stored_payload = await self._store_attachment_by_backend(
            guild_id=guild_id,
            attachment=attachment,
        )
        if not stored_payload:
            return None

        new_backend = str(stored_payload.get("storage_backend") or "local").strip().lower()
        new_stored_filename = str(stored_payload.get("stored_filename") or "").strip()
        new_external_url = str(stored_payload.get("external_url") or "").strip()
        new_external_id = str(stored_payload.get("external_id") or "").strip()
        new_storage_channel_id = int(stored_payload.get("storage_channel_id") or 0)
        new_storage_message_id = int(stored_payload.get("storage_message_id") or 0)
        new_storage_guild_id = int(stored_payload.get("storage_guild_id") or 0)
        new_mime_type = str(stored_payload.get("mime_type") or "application/octet-stream").strip().lower()[:120]
        new_file_size = int(stored_payload.get("file_size") or 0)
        new_mongodb_payload = stored_payload.get("mongodb_payload")

        if new_backend == "mongodb":
            payload_bytes = new_mongodb_payload if isinstance(new_mongodb_payload, (bytes, bytearray, memoryview)) else b""
            payload_bytes = bytes(payload_bytes or b"")
            if not payload_bytes:
                return None
            blob_ok = await self._upsert_mongodb_blob_for_asset(
                asset_id=asset_id,
                guild_id=guild_id,
                payload=payload_bytes,
                mime_type=new_mime_type,
                file_size=new_file_size,
            )
            if not blob_ok:
                return None

        updated = await photo_assets_db.update(
            id=asset_id,
            original_filename=str(getattr(attachment, "filename", "") or "").strip()[:255],
            stored_filename=new_stored_filename,
            external_url=new_external_url,
            external_id=new_external_id,
            storage_backend=new_backend,
            storage_channel_id=new_storage_channel_id,
            storage_message_id=new_storage_message_id,
            storage_guild_id=new_storage_guild_id,
            mime_type=new_mime_type,
            file_size=new_file_size,
            uploader_id=int(replaced_by or 0),
            source_message_id=int(source_message_id or 0),
            updated_at=_utc_now(),
        )
        if not updated:
            await self._cleanup_single_asset_storage(
                {
                    "id": 0,
                    "guild_id": guild_id,
                    "storage_backend": new_backend,
                    "stored_filename": new_stored_filename,
                    "storage_channel_id": new_storage_channel_id,
                    "storage_message_id": new_storage_message_id,
                    "external_id": new_external_id,
                },
                skip_mongodb_blob=True,
            )
            return None

        old_backend = str(asset.get("storage_backend") or "").strip().lower() or "local"
        same_discord_message = (
            old_backend == "discord_channel"
            and new_backend == "discord_channel"
            and int(asset.get("storage_channel_id") or 0) == int(updated.get("storage_channel_id") or 0)
            and int(asset.get("storage_message_id") or 0) == int(updated.get("storage_message_id") or 0)
        )
        same_mongo_asset = old_backend == "mongodb" and new_backend == "mongodb"
        if not same_discord_message and not same_mongo_asset:
            await self._cleanup_single_asset_storage(asset)

        if old_backend == "mongodb" and new_backend != "mongodb":
            try:
                await photo_asset_blobs_db.delete(asset_id=asset_id)
            except Exception:
                pass

        return updated

    async def replace_asset_from_button(
        self,
        *,
        interaction: discord.Interaction,
        asset: dict[str, Any],
    ) -> None:
        guild = interaction.guild
        channel = interaction.channel
        actor = interaction.user
        if guild is None or channel is None:
            return await self.safe_interaction_reply(
                interaction,
                "Cannot resolve room to replace photo.",
                ephemeral=True,
            )
        room, room_error = await self._can_actor_use_photoroom(guild=guild, actor=actor)
        if room is None:
            return await self.safe_interaction_reply(interaction, room_error or "PhotoRoom is unavailable", ephemeral=True)

        await self.safe_interaction_reply(
            interaction,
            "Send a new image in this room within 180 seconds to replace this photo.",
            ephemeral=True,
        )

        target_channel_id = int(getattr(channel, "id", 0) or 0)
        target_user_id = int(getattr(actor, "id", 0) or 0)
        target_guild_id = int(getattr(guild, "id", 0) or 0)

        def _message_check(message: discord.Message) -> bool:
            if int(getattr(getattr(message, "guild", None), "id", 0) or 0) != target_guild_id:
                return False
            if int(getattr(getattr(message, "channel", None), "id", 0) or 0) != target_channel_id:
                return False
            if int(getattr(getattr(message, "author", None), "id", 0) or 0) != target_user_id:
                return False
            return any(_is_image_attachment(item) for item in list(getattr(message, "attachments", []) or []))

        try:
            message = await self.bot.wait_for("message", check=_message_check, timeout=180)
        except asyncio.TimeoutError:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Timeout: no new image received. Please click `Edit Image` again.",
                    ephemeral=True,
                )
            return

        new_attachment: discord.Attachment | None = None
        for item in list(getattr(message, "attachments", []) or []):
            if _is_image_attachment(item):
                new_attachment = item
                break
        if new_attachment is None:
            if interaction.response.is_done():
                await interaction.followup.send("No valid image found. Please try again.", ephemeral=True)
            return

        updated = await self._replace_asset_attachment(
            asset=asset,
            attachment=new_attachment,
            replaced_by=int(getattr(actor, "id", 0) or 0),
            source_message_id=int(getattr(message, "id", 0) or 0),
        )
        if not updated:
            if interaction.response.is_done():
                await interaction.followup.send("Failed to replace image. Please try again.", ephemeral=True)
            return

        await self.refresh_asset_message(updated)
        url = self._photo_link(int(updated.get("guild_id") or 0), str(updated.get("slug") or ""))
        if interaction.response.is_done():
            await interaction.followup.send(
                f"Image replaced for `{updated.get('slug')}`\n{url}",
                ephemeral=True,
            )

    async def delete_asset_record(
        self,
        *,
        asset: dict[str, Any],
        deleted_by: int = 0,
        mark_control_message: bool = False,
    ) -> bool:
        if mark_control_message:
            await self._edit_control_message_deleted(asset)
        deleted_rows = await photo_assets_db.delete(id=int(asset.get("id") or 0))
        if not deleted_rows:
            return False
        for row in deleted_rows:
            await self._cleanup_single_asset_storage(row)
        if deleted_by:
            logger.info(
                "photoroom asset deleted | "
                f"guild={int(asset.get('guild_id') or 0)} "
                f"asset_id={int(asset.get('id') or 0)} "
                f"deleted_by={int(deleted_by)}"
            )
        return True

    async def _create_asset_from_attachment(
        self,
        *,
        guild: discord.Guild,
        room: discord.TextChannel,
        attachment: discord.Attachment,
        preferred_name: str,
        uploader_id: int,
        source_message_id: int = 0,
    ) -> dict[str, Any] | None:
        guild_id = int(guild.id)
        scope_guild_id = self._scope_guild_id(guild_id)
        unique_slug = await self._resolve_unique_slug(scope_guild_id=scope_guild_id, preferred=preferred_name)

        stored_payload = await self._store_attachment_by_backend(
            guild_id=guild_id,
            attachment=attachment,
        )
        if not stored_payload:
            return None
        stored_filename = str(stored_payload.get("stored_filename") or "").strip()
        file_size = int(stored_payload.get("file_size") or 0)
        mime_type = str(stored_payload.get("mime_type") or "").strip().lower()
        external_url = str(stored_payload.get("external_url") or "").strip()
        external_id = str(stored_payload.get("external_id") or "").strip()
        storage_backend = str(stored_payload.get("storage_backend") or "local").strip().lower()
        storage_channel_id = int(stored_payload.get("storage_channel_id") or 0)
        storage_message_id = int(stored_payload.get("storage_message_id") or 0)
        storage_guild_id = int(stored_payload.get("storage_guild_id") or 0)
        mongodb_payload = stored_payload.get("mongodb_payload")

        now = _utc_now()

        async def _insert_with_slug(target_slug: str) -> dict[str, Any] | None:
            return await photo_assets_db.insert(
                guild_id=guild_id,
                scope_guild_id=scope_guild_id,
                slug=target_slug,
                display_name=str(preferred_name or "").strip()[:120],
                original_filename=str(getattr(attachment, "filename", "") or "").strip()[:255],
                stored_filename=stored_filename,
                external_url=external_url,
                external_id=external_id,
                storage_backend=storage_backend,
                storage_channel_id=storage_channel_id,
                storage_message_id=storage_message_id,
                storage_guild_id=storage_guild_id,
                mime_type=mime_type[:120],
                file_size=int(file_size),
                uploader_id=int(uploader_id or 0),
                upload_channel_id=int(room.id),
                source_message_id=int(source_message_id or 0),
                created_at=now,
                updated_at=now,
            )

        inserted = await _insert_with_slug(unique_slug)
        if not inserted:
            await self._cleanup_single_asset_storage(
                {
                    "id": 0,
                    "guild_id": guild_id,
                    "storage_backend": storage_backend,
                    "stored_filename": stored_filename,
                    "storage_channel_id": storage_channel_id,
                    "storage_message_id": storage_message_id,
                    "external_id": external_id,
                },
                skip_mongodb_blob=True,
            )
            return None

        inserted_filename = str(inserted.get("stored_filename") or "")
        if inserted_filename != stored_filename:
            retry_slug = await self._resolve_unique_slug(
                scope_guild_id=scope_guild_id,
                preferred=f"{preferred_name}-{uuid.uuid4().hex[:4]}",
            )
            inserted = await _insert_with_slug(retry_slug)
            inserted_filename = str(inserted.get("stored_filename") or "") if inserted else ""
            if not inserted or inserted_filename != stored_filename:
                await self._cleanup_single_asset_storage(
                    {
                        "id": 0,
                        "guild_id": guild_id,
                        "storage_backend": storage_backend,
                        "stored_filename": stored_filename,
                        "storage_channel_id": storage_channel_id,
                        "storage_message_id": storage_message_id,
                        "external_id": external_id,
                    },
                    skip_mongodb_blob=True,
                )
                return None

        if storage_backend == "mongodb":
            payload_bytes = mongodb_payload if isinstance(mongodb_payload, (bytes, bytearray, memoryview)) else b""
            payload_bytes = bytes(payload_bytes or b"")
            if not payload_bytes:
                try:
                    await photo_assets_db.delete(id=int(inserted.get("id") or 0))
                except Exception:
                    pass
                return None
            blob_ok = await self._upsert_mongodb_blob_for_asset(
                asset_id=int(inserted["id"]),
                guild_id=guild_id,
                payload=payload_bytes,
                mime_type=mime_type[:120],
                file_size=int(file_size),
            )
            if not blob_ok:
                try:
                    await photo_assets_db.delete(id=int(inserted.get("id") or 0))
                except Exception:
                    pass
                return None

        used_after = await photo_assets_db.count(guild_id=guild_id)
        embed = self._build_asset_embed(
            guild_id=guild_id,
            asset=inserted,
            used=used_after,
            limit=self._plan_limit(guild_id),
        )
        try:
            sent = await room.send(embed=embed, view=PhotoAssetManageView(self))
        except Exception:
            await self.delete_asset_record(
                asset=inserted,
                deleted_by=0,
                mark_control_message=False,
            )
            return None
        updated = await photo_assets_db.update(
            id=int(inserted["id"]),
            control_message_id=int(sent.id),
            updated_at=_utc_now(),
        )
        return updated or inserted

    async def _find_guild_asset_by_slug(self, *, guild_id: int, slug_value: str) -> dict[str, Any] | None:
        scope_guild_id = self._scope_guild_id(guild_id)
        asset = await photo_assets_db.get(scope_guild_id=scope_guild_id, slug=slug_value)
        if not asset:
            return None
        if int(asset.get("guild_id") or 0) != int(guild_id):
            return None
        return asset

    async def _find_scope_asset_by_slug(
        self,
        *,
        guild_id: int,
        slug_value: str,
        exclude_id: int = 0,
    ) -> dict[str, Any] | None:
        scope_guild_id = self._scope_guild_id(guild_id)
        asset = await photo_assets_db.get(scope_guild_id=scope_guild_id, slug=slug_value)
        if not asset:
            return None
        asset_id = int(asset.get("id") or 0)
        if exclude_id > 0 and asset_id == int(exclude_id):
            return None
        return asset

    async def configure_room_from_setup_command(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")

        target_channel = channel
        created_new = False
        if target_channel is None:
            existing = await self._configured_room_channel(ctx.guild)
            if existing is not None:
                target_channel = existing
            else:
                created_channel, create_error = await self._auto_create_photoroom_channel(
                    guild=ctx.guild,
                    requester_channel=ctx.channel if isinstance(ctx.channel, discord.abc.GuildChannel) else None,
                )
                if created_channel is None:
                    return await self._safe_ctx_send(
                        ctx,
                        f"{create_error or 'Auto create room failed.'}\n"
                        "Please select a room with `/setup photoroom channel:#room`.",
                    )
                target_channel = created_channel
                created_new = True

        if target_channel is None:
            return await self._safe_ctx_send(ctx, "Please choose a text channel.")

        me = ctx.guild.me
        if me is None:
            return await self._safe_ctx_send(ctx, "Bot is not ready yet.")
        bot_permissions = target_channel.permissions_for(me)
        if not bot_permissions.view_channel or not bot_permissions.send_messages:
            return await self._safe_ctx_send(
                ctx,
                f"Bot cannot send messages in {target_channel.mention}. Please grant permission first.",
            )

        await self._upsert_photoroom_channel(
            guild_id=int(ctx.guild.id),
            channel_id=int(target_channel.id),
            updated_by=int(getattr(ctx.author, "id", 0)),
        )

        preview_url = self._photo_link(ctx.guild.id, "example-image")
        embed = discord.Embed(
            title="PhotoRoom Configured",
            description=(
                f"Upload room: {target_channel.mention}\n"
                f"{'Auto-created new room for you.' if created_new else 'Room updated successfully.'}\n"
                f"Example URL: {preview_url}"
            ),
            color=color.green,
        )
        embed.set_footer(text=f"Plan limit: {self._plan_limit(ctx.guild.id)} images")
        await self._safe_ctx_send(ctx, embed=embed)

    @commands.hybrid_group(
        name="photoroom",
        help="Manage photoroom setup",
        with_app_command=True,
        invoke_without_command=True,
    )
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.guild)
    async def photoroom_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._safe_ctx_send(ctx, "Use `/setup photoroom` to configure room.")

    @photoroom_group.command(name="setup", with_app_command=True, help="Set PhotoRoom channel")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def photoroom_setup(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if member is None or not (member.guild_permissions.manage_guild or member.guild_permissions.administrator):
            return await self._safe_ctx_send(ctx, "You need Manage Server permission.")
        await self._safe_ctx_defer(ctx)
        await self.configure_room_from_setup_command(ctx, channel)

    @photoroom_group.command(name="remove", with_app_command=True, help="Disable PhotoRoom")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def photoroom_remove(self, ctx: commands.Context):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if member is None or not (member.guild_permissions.manage_guild or member.guild_permissions.administrator):
            return await self._safe_ctx_send(ctx, "You need Manage Server permission.")
        await self._safe_ctx_defer(ctx)
        await photoroom_channels_db.delete(guild_id=int(ctx.guild.id))
        await self._safe_ctx_send(ctx, "PhotoRoom disabled for this server.")

    @commands.hybrid_group(
        name="photourl",
        help="Manage photo URLs",
        with_app_command=True,
        invoke_without_command=True,
    )
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def photourl_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._safe_ctx_send(
            ctx,
            "Available: `/photourl create`, `/photourl list`, `/photourl edit`, `/photourl delist`",
        )

    @photourl_group.command(name="create", with_app_command=True, help="Create photo URL from image")
    async def photourl_create(
        self,
        ctx: commands.Context,
        image: discord.Attachment | None = None,
        name: str | None = None,
    ):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        await self._safe_ctx_defer(ctx)
        room, room_error = await self._can_actor_use_photoroom(guild=ctx.guild, actor=ctx.author)
        if room is None:
            return await self._safe_ctx_send(ctx, room_error or "PhotoRoom is unavailable")

        attachment = image
        if attachment is None and ctx.message and ctx.message.attachments:
            for item in ctx.message.attachments:
                if _is_image_attachment(item):
                    attachment = item
                    break
        if attachment is None:
            return await self._safe_ctx_send(ctx, "Please attach an image to create URL.")
        if not _is_image_attachment(attachment):
            return await self._safe_ctx_send(ctx, "Only image files are supported.")

        used_count = await photo_assets_db.count(guild_id=int(ctx.guild.id))
        plan_limit = self._plan_limit(ctx.guild.id)
        if int(used_count) >= int(plan_limit):
            return await self._safe_ctx_send(
                ctx,
                f"Photo limit reached for plan `{self._plan_display(ctx.guild.id)}` ({used_count}/{plan_limit}).",
            )

        preferred_name = str(name or "").strip() or _filename_stem(str(getattr(attachment, "filename", "") or ""))
        preferred_slug = _slugify_photo_name(preferred_name, fallback="photo")
        duplicate_asset = await self._find_scope_asset_by_slug(
            guild_id=int(ctx.guild.id),
            slug_value=preferred_slug,
        )
        if duplicate_asset:
            duplicate_url = self._photo_link(int(duplicate_asset.get("guild_id") or ctx.guild.id), preferred_slug)
            return await self._safe_ctx_send(
                ctx,
                (
                    f"Photo URL `{preferred_slug}` already exists.\n"
                    f"{duplicate_url}\n"
                    "Use `/photourl edit` to replace image or choose another name."
                ),
            )

        created = await self._create_asset_from_attachment(
            guild=ctx.guild,
            room=room,
            attachment=attachment,
            preferred_name=preferred_name,
            uploader_id=int(getattr(ctx.author, "id", 0) or 0),
            source_message_id=int(getattr(getattr(ctx, "message", None), "id", 0) or 0),
        )
        if not created:
            active_backend = self._storage_backend_label(self._storage_backend())
            return await self._safe_ctx_send(
                ctx,
                f"Failed to create photo URL. Please check backend settings (`{active_backend}`).",
            )

        url = self._photo_link(int(created.get("guild_id") or 0), str(created.get("slug") or ""))
        storage_label = self._storage_backend_label(str(created.get("storage_backend") or ""))
        await self._safe_ctx_send(
            ctx,
            f"Created `{created.get('slug')}`\n{url}\nSaved in {room.mention}\nBackend: `{storage_label}`",
        )

    @photourl_group.command(name="craednt", with_app_command=True, help="Alias of /photourl create")
    async def photourl_craednt(
        self,
        ctx: commands.Context,
        image: discord.Attachment | None = None,
        name: str | None = None,
    ):
        await self.photourl_create(ctx, image=image, name=name)

    @photourl_group.command(name="list", with_app_command=True, help="List photo URLs")
    async def photourl_list(self, ctx: commands.Context):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        await self._safe_ctx_defer(ctx)
        room, room_error = await self._can_actor_use_photoroom(guild=ctx.guild, actor=ctx.author)
        if room is None:
            return await self._safe_ctx_send(ctx, room_error or "PhotoRoom is unavailable")

        assets = await photo_assets_db.gets(guild_id=int(ctx.guild.id))
        if not assets:
            return await self._safe_ctx_send(ctx, "No photo URL saved in this server.")

        lines: list[str] = []
        max_items = 20
        for index, asset in enumerate(assets[:max_items], start=1):
            slug = str(asset.get("slug") or "").strip()
            url = self._photo_link(ctx.guild.id, slug)
            lines.append(f"`{index}.` `{slug}` -> [open]({url})")

        total = len(assets)
        plan_limit = self._plan_limit(ctx.guild.id)
        description = "\n".join(lines)
        if total > max_items:
            description += f"\n... and {total - max_items} more"

        embed = discord.Embed(
            title="Photo URL List",
            description=description[:4000],
            color=color.blue,
        )
        embed.set_footer(text=f"Total: {total}/{plan_limit} | PhotoRoom: #{room.name}")
        await self._safe_ctx_send(ctx, embed=embed)

    @photourl_group.command(name="edit", with_app_command=True, help="Rename photo URL and/or replace image")
    async def photourl_edit(
        self,
        ctx: commands.Context,
        current_name: str,
        new_name: str | None = None,
        image: discord.Attachment | None = None,
    ):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        await self._safe_ctx_defer(ctx)
        room, room_error = await self._can_actor_use_photoroom(guild=ctx.guild, actor=ctx.author)
        if room is None:
            return await self._safe_ctx_send(ctx, room_error or "PhotoRoom is unavailable")

        current_slug = _slugify_photo_name(current_name, fallback="photo")
        asset = await self._find_guild_asset_by_slug(guild_id=int(ctx.guild.id), slug_value=current_slug)
        if not asset:
            return await self._safe_ctx_send(ctx, f"Photo `{current_slug}` not found.")

        attachment = image
        if attachment is None and ctx.message and ctx.message.attachments:
            for item in ctx.message.attachments:
                if _is_image_attachment(item):
                    attachment = item
                    break

        if not str(new_name or "").strip() and attachment is None:
            return await self._safe_ctx_send(
                ctx,
                "Provide `new_name`, `image`, or both.\nExample: `/photourl edit current_name:ocr new_name:ocr-main image:<file>`",
            )

        working_asset = asset
        updates: list[str] = []

        if str(new_name or "").strip():
            desired_slug = _slugify_photo_name(str(new_name or "").strip(), fallback="photo")
            current_asset_slug = str(working_asset.get("slug") or "").strip()
            if desired_slug != current_asset_slug:
                duplicate_asset = await self._find_scope_asset_by_slug(
                    guild_id=int(ctx.guild.id),
                    slug_value=desired_slug,
                    exclude_id=int(working_asset.get("id") or 0),
                )
                if duplicate_asset:
                    duplicate_url = self._photo_link(
                        int(duplicate_asset.get("guild_id") or ctx.guild.id),
                        desired_slug,
                    )
                    return await self._safe_ctx_send(
                        ctx,
                        f"Photo URL `{desired_slug}` already exists.\n{duplicate_url}",
                    )
                renamed = await photo_assets_db.update(
                    id=int(working_asset["id"]),
                    slug=desired_slug,
                    display_name=str(new_name or "").strip()[:120],
                    updated_at=_utc_now(),
                )
                if not renamed:
                    return await self._safe_ctx_send(ctx, "Failed to update photo name.")
                working_asset = renamed
                updates.append(f"renamed to `{desired_slug}`")

        if attachment is not None:
            if not _is_image_attachment(attachment):
                return await self._safe_ctx_send(ctx, "Only image files are supported for `image`.")
            replaced = await self._replace_asset_attachment(
                asset=working_asset,
                attachment=attachment,
                replaced_by=int(getattr(ctx.author, "id", 0) or 0),
                source_message_id=int(getattr(getattr(ctx, "message", None), "id", 0) or 0),
            )
            if not replaced:
                return await self._safe_ctx_send(ctx, "Failed to replace image.")
            working_asset = replaced
            updates.append("image replaced")

        await self.refresh_asset_message(working_asset)
        result_slug = str(working_asset.get("slug") or "").strip() or current_slug
        new_url = self._photo_link(ctx.guild.id, result_slug)
        if not updates:
            updates.append("no changes")
        await self._safe_ctx_send(
            ctx,
            f"Updated `{current_slug}`: {', '.join(updates)}\n{new_url}",
        )

    @photourl_group.command(
        name="delist",
        aliases=["delete"],
        with_app_command=True,
        help="Delete photo URL",
    )
    async def photourl_delist(self, ctx: commands.Context, name: str):
        if not ctx.guild:
            return await self._safe_ctx_send(ctx, "This command works only in a server.")
        await self._safe_ctx_defer(ctx)
        room, room_error = await self._can_actor_use_photoroom(guild=ctx.guild, actor=ctx.author)
        if room is None:
            return await self._safe_ctx_send(ctx, room_error or "PhotoRoom is unavailable")

        slug = _slugify_photo_name(name, fallback="photo")
        asset = await self._find_guild_asset_by_slug(guild_id=int(ctx.guild.id), slug_value=slug)
        if not asset:
            return await self._safe_ctx_send(ctx, f"Photo `{slug}` not found.")

        deleted = await self.delete_asset_record(
            asset=asset,
            deleted_by=int(getattr(ctx.author, "id", 0) or 0),
            mark_control_message=True,
        )
        if not deleted:
            return await self._safe_ctx_send(ctx, "Failed to delete photo URL.")
        await self._safe_ctx_send(ctx, f"Deleted photo URL `{slug}`")

    @photoroom_group.command(name="delete", with_app_command=True, help="Delete photo URL")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def photoroom_delete(self, ctx: commands.Context, name: str):
        await self.photourl_delist(ctx, name)


async def setup(bot):
    await bot.add_cog(PhotoRoom(bot))


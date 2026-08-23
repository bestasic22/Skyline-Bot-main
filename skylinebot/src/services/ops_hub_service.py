from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import storage.ops_hub_records as ops_hub_db


class OpsHubService:
    """Shared persistence helpers for enterprise operation features."""

    CONFIG_KIND = "config"
    HEALTH_KIND = "health_daily"

    def __init__(self, bot):
        self.bot = bot
        self._config_cache: dict[tuple[int, str], tuple[float, dict[str, Any]]] = {}
        self._config_cache_ttl_seconds = 20.0
        self._last_trust_award_at: dict[tuple[int, int], float] = {}
        self._trust_award_cooldown_seconds = 90.0

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def now_iso(cls) -> str:
        return cls.now_utc().replace(microsecond=0).isoformat()

    @staticmethod
    def _build_key(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:10]}"

    @staticmethod
    def _config_cache_key(guild_id: int, key: str) -> tuple[int, str]:
        return int(guild_id), str(key).strip().lower()

    @staticmethod
    def _date_key(date_value: datetime | None = None) -> str:
        src = date_value or datetime.now(timezone.utc)
        return src.strftime("%Y-%m-%d")

    def _cache_get(self, guild_id: int, key: str) -> dict[str, Any] | None:
        cache_key = self._config_cache_key(guild_id, key)
        cached = self._config_cache.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if self.now_utc().timestamp() > expires_at:
            self._config_cache.pop(cache_key, None)
            return None
        return deepcopy(payload)

    def _cache_put(self, guild_id: int, key: str, payload: dict[str, Any]) -> None:
        cache_key = self._config_cache_key(guild_id, key)
        expires_at = self.now_utc().timestamp() + self._config_cache_ttl_seconds
        self._config_cache[cache_key] = (expires_at, deepcopy(payload))

    async def get_config_data(
        self,
        guild_id: int,
        key: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cached = self._cache_get(guild_id, key)
        if cached is not None:
            return cached

        row = await ops_hub_db.get(
            guild_id=int(guild_id),
            kind=self.CONFIG_KIND,
            key=str(key).strip().lower(),
        )
        if not row:
            payload = deepcopy(default if isinstance(default, dict) else {})
            self._cache_put(guild_id, key, payload)
            return payload

        data = row.get("data")
        payload = deepcopy(data if isinstance(data, dict) else {})
        self._cache_put(guild_id, key, payload)
        return payload

    async def set_config_data(self, guild_id: int, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        guild_id = int(guild_id)
        config_key = str(key).strip().lower()
        data = deepcopy(payload if isinstance(payload, dict) else {})
        row = await ops_hub_db.get(guild_id=guild_id, kind=self.CONFIG_KIND, key=config_key)
        if row and row.get("id"):
            await ops_hub_db.update(
                id=row["id"],
                guild_id=guild_id,
                kind=self.CONFIG_KIND,
                key=config_key,
                data=data,
                updated_at=self.now_utc(),
            )
        else:
            await ops_hub_db.insert(
                guild_id=guild_id,
                kind=self.CONFIG_KIND,
                key=config_key,
                status="active",
                data=data,
                updated_at=self.now_utc(),
            )
        self._cache_put(guild_id, config_key, data)
        return data

    async def create_record(
        self,
        *,
        guild_id: int,
        kind: str,
        data: dict[str, Any] | None = None,
        status: str = "open",
        actor_id: int | None = None,
        user_id: int | None = None,
        reference_id: int | None = None,
        key: str | None = None,
    ) -> dict[str, Any]:
        created = await ops_hub_db.insert(
            guild_id=int(guild_id),
            kind=str(kind).strip().lower(),
            key=str(key).strip().lower() if key else self._build_key(kind),
            status=str(status).strip().lower(),
            actor_id=int(actor_id) if actor_id is not None else None,
            user_id=int(user_id) if user_id is not None else None,
            reference_id=int(reference_id) if reference_id is not None else None,
            data=deepcopy(data if isinstance(data, dict) else {}),
            updated_at=self.now_utc(),
        )
        return created or {}

    async def get_record(self, *, guild_id: int, kind: str, record_id: int) -> dict[str, Any] | None:
        row = await ops_hub_db.get(
            id=int(record_id),
            guild_id=int(guild_id),
            kind=str(kind).strip().lower(),
        )
        return row

    async def list_records(
        self,
        *,
        guild_id: int,
        kind: str,
        status: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        rows = await ops_hub_db.gets(guild_id=int(guild_id), kind=str(kind).strip().lower())
        if status:
            status_norm = str(status).strip().lower()
            rows = [item for item in rows if str(item.get("status") or "").strip().lower() == status_norm]
        rows = sorted(rows, key=lambda item: int(item.get("id") or 0), reverse=True)
        return rows[: max(1, int(limit))]

    async def update_record(
        self,
        record_id: int,
        *,
        status: str | None = None,
        data: dict[str, Any] | None = None,
        actor_id: int | None = None,
        user_id: int | None = None,
        reference_id: int | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"id": int(record_id), "updated_at": self.now_utc()}
        if status is not None:
            payload["status"] = str(status).strip().lower()
        if data is not None:
            payload["data"] = deepcopy(data if isinstance(data, dict) else {})
        if actor_id is not None:
            payload["actor_id"] = int(actor_id)
        if user_id is not None:
            payload["user_id"] = int(user_id)
        if reference_id is not None:
            payload["reference_id"] = int(reference_id)
        return await ops_hub_db.update(**payload)

    async def mark_onboard_stage(self, guild_id: int, stage: str, amount: int = 1) -> dict[str, Any]:
        stats = await self.get_config_data(
            guild_id,
            "onboard_stats",
            {
                "joined": 0,
                "verified": 0,
                "role_assigned": 0,
                "first_message": 0,
                "updated_at": self.now_iso(),
            },
        )
        key = str(stage).strip().lower()
        stats[key] = max(0, int(stats.get(key, 0)) + int(amount))
        stats["updated_at"] = self.now_iso()
        return await self.set_config_data(guild_id, "onboard_stats", stats)

    async def get_onboard_stats(self, guild_id: int) -> dict[str, Any]:
        return await self.get_config_data(
            guild_id,
            "onboard_stats",
            {
                "joined": 0,
                "verified": 0,
                "role_assigned": 0,
                "first_message": 0,
                "updated_at": self.now_iso(),
            },
        )

    async def mark_first_message(self, guild_id: int, user_id: int) -> bool:
        key = str(int(user_id))
        existing = await ops_hub_db.get(guild_id=int(guild_id), kind="onboard_member", key=key)
        if existing:
            return False
        await ops_hub_db.insert(
            guild_id=int(guild_id),
            kind="onboard_member",
            key=key,
            status="active",
            user_id=int(user_id),
            data={"first_message_at": self.now_iso()},
            updated_at=self.now_utc(),
        )
        return True

    async def bump_health_metric(self, guild_id: int, metric: str, amount: int = 1) -> dict[str, Any]:
        metric_key = str(metric).strip().lower()
        date_key = self._date_key()
        row = await ops_hub_db.get(guild_id=int(guild_id), kind=self.HEALTH_KIND, key=date_key)
        if not row:
            data = {
                metric_key: max(0, int(amount)),
                "date": date_key,
                "updated_at": self.now_iso(),
            }
            await ops_hub_db.insert(
                guild_id=int(guild_id),
                kind=self.HEALTH_KIND,
                key=date_key,
                status="active",
                data=data,
                updated_at=self.now_utc(),
            )
            return data

        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        data = deepcopy(data)
        data[metric_key] = max(0, int(data.get(metric_key, 0)) + int(amount))
        data["date"] = date_key
        data["updated_at"] = self.now_iso()
        await ops_hub_db.update(id=row["id"], data=data, updated_at=self.now_utc())
        return data

    async def get_health_summary(self, guild_id: int, days: int = 1) -> dict[str, Any]:
        safe_days = max(1, min(int(days), 31))
        rows = await ops_hub_db.gets(guild_id=int(guild_id), kind=self.HEALTH_KIND)
        if not rows:
            return {"days": safe_days, "totals": {}}

        wanted_dates = {
            self._date_key(self.now_utc() - timedelta(days=offset))
            for offset in range(safe_days)
        }
        totals: dict[str, int] = {}
        for row in rows:
            key = str(row.get("key") or "")
            if key not in wanted_dates:
                continue
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            for metric, value in data.items():
                if metric in {"date", "updated_at"}:
                    continue
                totals[metric] = totals.get(metric, 0) + int(value or 0)
        return {"days": safe_days, "totals": totals}

    async def get_trust_rules(self, guild_id: int) -> dict[str, Any]:
        return await self.get_config_data(
            guild_id,
            "trust_rules",
            {
                "enabled": True,
                "silver_threshold": 30,
                "gold_threshold": 70,
                "silver_role_id": 0,
                "gold_role_id": 0,
                "message_gain": 1,
            },
        )

    async def set_trust_rules(self, guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_trust_rules(guild_id)
        merged = deepcopy(current)
        merged.update(payload or {})
        merged["silver_threshold"] = max(1, int(merged.get("silver_threshold", 30)))
        merged["gold_threshold"] = max(merged["silver_threshold"], int(merged.get("gold_threshold", 70)))
        merged["silver_role_id"] = max(0, int(merged.get("silver_role_id", 0) or 0))
        merged["gold_role_id"] = max(0, int(merged.get("gold_role_id", 0) or 0))
        merged["message_gain"] = max(0, min(10, int(merged.get("message_gain", 1) or 1)))
        merged["enabled"] = bool(merged.get("enabled", True))
        return await self.set_config_data(guild_id, "trust_rules", merged)

    @staticmethod
    def trust_tier(score: int, silver_threshold: int, gold_threshold: int) -> str:
        if score >= int(gold_threshold):
            return "gold"
        if score >= int(silver_threshold):
            return "silver"
        return "new"

    async def get_trust_profile(self, guild_id: int, user_id: int) -> dict[str, Any]:
        key = str(int(user_id))
        row = await ops_hub_db.get(guild_id=int(guild_id), kind="trust_profile", key=key)
        if row and isinstance(row.get("data"), dict):
            return row

        rules = await self.get_trust_rules(guild_id)
        score = 10
        tier = self.trust_tier(score, rules["silver_threshold"], rules["gold_threshold"])
        created = await ops_hub_db.insert(
            guild_id=int(guild_id),
            kind="trust_profile",
            key=key,
            status="active",
            user_id=int(user_id),
            data={
                "score": score,
                "tier": tier,
                "updated_at": self.now_iso(),
            },
            updated_at=self.now_utc(),
        )
        return created or {}

    async def adjust_trust_score(self, guild_id: int, user_id: int, delta: int) -> dict[str, Any]:
        row = await self.get_trust_profile(guild_id, user_id)
        if not row:
            return {}

        rules = await self.get_trust_rules(guild_id)
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        score = max(0, min(100, int(data.get("score", 10)) + int(delta)))
        tier = self.trust_tier(score, rules["silver_threshold"], rules["gold_threshold"])
        data = deepcopy(data)
        data["score"] = score
        data["tier"] = tier
        data["updated_at"] = self.now_iso()
        await ops_hub_db.update(id=row["id"], data=data, updated_at=self.now_utc())
        row["data"] = data
        return row

    def should_award_trust(self, guild_id: int, user_id: int) -> bool:
        key = (int(guild_id), int(user_id))
        now_ts = self.now_utc().timestamp()
        last_ts = self._last_trust_award_at.get(key, 0.0)
        if now_ts - last_ts < self._trust_award_cooldown_seconds:
            return False
        self._last_trust_award_at[key] = now_ts
        return True

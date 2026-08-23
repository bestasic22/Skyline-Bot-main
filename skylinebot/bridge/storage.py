from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import os
import time
from functools import cmp_to_key
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from motor.motor_asyncio import AsyncIOMotorClient

from skylinebot.console.logging import logger
from skylinebot.config.config import storage as StorageConfig

_client: AsyncIOMotorClient | None = None
_database = None
_cluster_clients: list[tuple[str, AsyncIOMotorClient]] | None = None
_cluster_databases: list[tuple[str, Any, AsyncIOMotorClient]] | None = None
_cluster_databases_key: tuple[str, ...] | None = None
_database_key: tuple[str, ...] | None = None
_storage_settings = StorageConfig()
_last_connect_error: Exception | None = None
_last_connect_error_at: float = 0.0
_cluster_io_metrics: dict[str, dict[str, Any]] = {}
_connect_clients_lock = asyncio.Lock()
_connect_clients_inflight: asyncio.Task[list[tuple[str, AsyncIOMotorClient]]] | None = None
_backup_warmup_task: asyncio.Task[None] | None = None


def _split_uri_values(raw_value: str) -> list[str]:
    values: list[str] = []
    for part in str(raw_value or "").replace("\n", ",").replace(";", ",").split(","):
        item = _clean_env_text(part or "")
        if not item or item in values:
            continue
        values.append(item)
    return values


def _clean_env_text(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        parsed = int(float(raw))
    except Exception:
        parsed = int(default)
    return max(min_value, min(parsed, max_value))


def _looks_placeholder_uri(uri: str) -> bool:
    return "@cluster.mongodb.net" in uri


def _mask_uri_host(uri: str) -> str:
    try:
        parsed = urlparse(uri)
        return parsed.hostname or "unknown-host"
    except Exception:
        return "unknown-host"


def _candidate_uris() -> list[str]:
    candidates: list[str] = []
    primary = _clean_env_text(
        os.getenv("MONGO_SRV")
        or os.getenv("MONGO_URI")
        or _storage_settings.uri
        or ""
    )
    backup_raw = _clean_env_text(os.getenv("MONGO_URI_BACKUP", _storage_settings.uri_backup or "") or "")

    if primary:
        candidates.append(primary)

    for item in _split_uri_values(backup_raw):
        if item not in candidates:
            candidates.append(item)

    return candidates


def _parse_collection_route_indexes(raw_value: str, *, total: int) -> list[int]:
    indexes: list[int] = []
    for part in str(raw_value or "").replace("|", ",").split(","):
        token = str(part or "").strip().lower()
        if not token:
            continue
        token = token.removeprefix("db").removeprefix("#")
        try:
            idx = int(token)
        except Exception:
            continue
        if idx < 1 or idx > max(1, int(total)):
            continue
        if idx not in indexes:
            indexes.append(idx)
    return indexes


def _parse_collection_route_rules(raw_value: str, *, total: int) -> list[tuple[str, list[int]]]:
    rules: list[tuple[str, list[int]]] = []
    if total <= 1:
        return rules
    text = str(raw_value or "").replace("\r", "\n").replace(";", "\n")
    for line in text.split("\n"):
        row = str(line or "").strip()
        if not row or row.startswith("#"):
            continue
        if "=" not in row:
            continue
        pattern_text, indexes_text = row.split("=", 1)
        pattern = str(pattern_text or "").strip().lower()
        if not pattern:
            continue
        indexes = _parse_collection_route_indexes(indexes_text, total=total)
        if not indexes:
            continue
        rules.append((pattern, indexes))
    return rules


def _route_collection_refs(
    collection_name: str,
    refs: list[tuple[str, Any, AsyncIOMotorClient]],
) -> tuple[list[tuple[str, Any, AsyncIOMotorClient]], bool]:
    if len(refs) <= 1:
        return list(refs), False
    route_text = _clean_env_text(os.getenv("MONGO_MULTI_COLLECTION_ROUTE", "") or "")
    if not route_text:
        return list(refs), False

    collection_key = str(collection_name or "").strip().lower()
    if not collection_key:
        return list(refs), False

    rules = _parse_collection_route_rules(route_text, total=len(refs))
    if not rules:
        return list(refs), False

    for pattern, indexes in rules:
        matched = False
        if "*" in pattern:
            matched = fnmatch.fnmatch(collection_key, pattern)
        else:
            matched = collection_key == pattern
        if not matched:
            continue

        mapped_refs: list[tuple[str, Any, AsyncIOMotorClient]] = []
        for idx in indexes:
            zero_index = max(0, int(idx) - 1)
            if zero_index >= len(refs):
                continue
            mapped_refs.append(refs[zero_index])
        if mapped_refs:
            return mapped_refs, True
    return list(refs), False


def mongo_database_name() -> str:
    explicit_name = _clean_env_text(os.getenv("MONGO_NAME") or "")
    if explicit_name:
        return explicit_name

    for uri in _candidate_uris():
        try:
            uri_name = unquote(urlparse(uri).path.lstrip("/").split("/", 1)[0]).strip()
        except Exception:
            uri_name = ""
        if uri_name and uri_name.lower() not in {"admin", "local", "config"}:
            return uri_name

    configured_name = _clean_env_text(_storage_settings.name or "")
    return configured_name or "skylinebot"


def mongo_candidate_uris() -> list[str]:
    return list(_candidate_uris())


def mongo_uri_host(uri: str) -> str:
    return _mask_uri_host(uri)


def mongo_backup_uri_text() -> str:
    return _clean_env_text(os.getenv("MONGO_URI_BACKUP", _storage_settings.uri_backup or "") or "")


def _ensure_cluster_metric_bucket(uri: str) -> dict[str, Any]:
    key = _clean_env_text(uri or "")
    bucket = _cluster_io_metrics.get(key)
    if bucket is None:
        bucket = {
            "read_ok": 0,
            "read_fail": 0,
            "write_ok": 0,
            "write_fail": 0,
            "last_error": "",
            "last_error_at": 0.0,
            "last_read_at": 0.0,
            "last_write_at": 0.0,
        }
        _cluster_io_metrics[key] = bucket
    return bucket


def _record_cluster_io(uri: str, *, io_kind: str, ok: bool, error: Exception | str | None = None) -> None:
    kind = str(io_kind or "").strip().lower()
    if kind not in {"read", "write"}:
        return
    bucket = _ensure_cluster_metric_bucket(uri)
    now_ts = float(time.time())
    status_key = f"{kind}_{'ok' if ok else 'fail'}"
    bucket[status_key] = int(bucket.get(status_key) or 0) + 1
    bucket[f"last_{kind}_at"] = now_ts
    if not ok:
        error_text = str(error or "").strip()
        bucket["last_error"] = error_text[:600]
        bucket["last_error_at"] = now_ts


def _success_rate(ok_count: int, fail_count: int) -> float | None:
    total = max(0, int(ok_count)) + max(0, int(fail_count))
    if total <= 0:
        return None
    return round((max(0, int(ok_count)) / float(total)) * 100.0, 2)


def mongo_cluster_health_snapshot() -> dict[str, Any]:
    uris = _candidate_uris()
    rows: list[dict[str, Any]] = []
    read_ok_total = 0
    read_fail_total = 0
    write_ok_total = 0
    write_fail_total = 0

    for idx, uri in enumerate(uris, start=1):
        bucket = _ensure_cluster_metric_bucket(uri)
        row_read_ok = int(bucket.get("read_ok") or 0)
        row_read_fail = int(bucket.get("read_fail") or 0)
        row_write_ok = int(bucket.get("write_ok") or 0)
        row_write_fail = int(bucket.get("write_fail") or 0)
        row_read_total = row_read_ok + row_read_fail
        row_write_total = row_write_ok + row_write_fail
        read_ok_total += row_read_ok
        read_fail_total += row_read_fail
        write_ok_total += row_write_ok
        write_fail_total += row_write_fail
        rows.append(
            {
                "index": idx,
                "host": _mask_uri_host(uri),
                "read_ok": row_read_ok,
                "read_fail": row_read_fail,
                "write_ok": row_write_ok,
                "write_fail": row_write_fail,
                "read_total": row_read_total,
                "write_total": row_write_total,
                "read_success_rate": _success_rate(row_read_ok, row_read_fail),
                "write_success_rate": _success_rate(row_write_ok, row_write_fail),
                "last_error": str(bucket.get("last_error") or ""),
                "last_error_at": float(bucket.get("last_error_at") or 0.0),
                "last_read_at": float(bucket.get("last_read_at") or 0.0),
                "last_write_at": float(bucket.get("last_write_at") or 0.0),
            }
        )

    return {
        "rows": rows,
        "totals": {
            "read_ok": int(read_ok_total),
            "read_fail": int(read_fail_total),
            "write_ok": int(write_ok_total),
            "write_fail": int(write_fail_total),
            "read_total": int(read_ok_total + read_fail_total),
            "write_total": int(write_ok_total + write_fail_total),
            "read_success_rate": _success_rate(read_ok_total, read_fail_total),
            "write_success_rate": _success_rate(write_ok_total, write_fail_total),
        },
    }


def mongo_set_runtime_uris(primary_uri: str, backup_uris: list[str] | tuple[str, ...]) -> None:
    primary = _clean_env_text(primary_uri or "")
    backups: list[str] = []
    for item in list(backup_uris or []):
        uri = _clean_env_text(item or "")
        if not uri or uri == primary or uri in backups:
            continue
        backups.append(uri)

    os.environ["MONGO_URI"] = primary
    os.environ["MONGO_URI_BACKUP"] = ",".join(backups)
    _storage_settings.uri = primary
    _storage_settings.uri_backup = ",".join(backups)


def mongo_reset_runtime_connections() -> None:
    global _client, _database, _cluster_clients, _cluster_databases, _cluster_databases_key, _database_key, _last_connect_error, _last_connect_error_at, _connect_clients_inflight, _backup_warmup_task
    existing_clients: dict[int, AsyncIOMotorClient] = {}
    if _client is not None:
        existing_clients[id(_client)] = _client
    for _uri, cluster_client in list(_cluster_clients or []):
        if cluster_client is None:
            continue
        existing_clients[id(cluster_client)] = cluster_client

    _client = None
    _database = None
    _cluster_clients = None
    _cluster_databases = None
    _cluster_databases_key = None
    _database_key = None
    _cluster_io_metrics.clear()
    _last_connect_error = None
    _last_connect_error_at = 0.0
    if _connect_clients_inflight is not None and not _connect_clients_inflight.done():
        _connect_clients_inflight.cancel()
    _connect_clients_inflight = None
    if _backup_warmup_task is not None and not _backup_warmup_task.done():
        _backup_warmup_task.cancel()
    _backup_warmup_task = None
    for existing in list(existing_clients.values()):
        try:
            existing.close()
        except Exception:
            pass


def _server_selection_timeout_ms() -> int:
    return _env_int("MONGO_SERVER_SELECTION_TIMEOUT_MS", 3000, min_value=1000, max_value=30000)


def _connect_timeout_ms() -> int:
    return _env_int("MONGO_CONNECT_TIMEOUT_MS", 10000, min_value=1000, max_value=120000)


def _socket_timeout_ms() -> int:
    return _env_int("MONGO_SOCKET_TIMEOUT_MS", 20000, min_value=1000, max_value=120000)


def _retry_cooldown_seconds() -> float:
    raw = str(os.getenv("MONGO_RETRY_COOLDOWN_SECONDS", "30") or "30").strip()
    try:
        parsed = float(raw)
    except Exception:
        parsed = 30.0
    return max(0.0, min(parsed, 600.0))


def _uri_declares_tls(uri: str) -> bool | None:
    try:
        parsed = urlparse(uri)
    except Exception:
        return None

    scheme = str(parsed.scheme or "").strip().lower()
    if scheme == "mongodb+srv":
        return True

    query = parse_qs(str(parsed.query or ""), keep_blank_values=False)
    for key in ("tls", "ssl"):
        values = query.get(key)
        if not values:
            continue
        value = str(values[-1] or "").strip().lower()
        if value in {"1", "true", "yes", "on", "y"}:
            return True
        if value in {"0", "false", "no", "off", "n"}:
            return False
    return None


def _normalize_read_preference_mode(value: str) -> str | None:
    raw = str(value or "").strip().lower()
    mapping = {
        "primary": "primary",
        "primarypreferred": "primaryPreferred",
        "secondary": "secondary",
        "secondarypreferred": "secondaryPreferred",
        "nearest": "nearest",
    }
    return mapping.get(raw)


def _uri_declares_read_preference(uri: str) -> str | None:
    try:
        parsed = urlparse(uri)
    except Exception:
        return None
    query = parse_qs(str(parsed.query or ""), keep_blank_values=False)
    for key in ("readPreference", "readpreference"):
        values = query.get(key)
        if not values:
            continue
        parsed_mode = _normalize_read_preference_mode(values[-1])
        if parsed_mode:
            return parsed_mode
    return None


def _preferred_read_preference(uri: str) -> str | None:
    env_mode = _normalize_read_preference_mode(_clean_env_text(os.getenv("MONGO_READ_PREFERENCE", "") or ""))
    if env_mode:
        return env_mode
    # Default to primaryPreferred for higher availability during elections.
    if _uri_declares_read_preference(uri):
        return None
    return "primaryPreferred"


def _default_tls_ca_file() -> str:
    try:
        import certifi  # type: ignore

        return str(certifi.where() or "").strip()
    except Exception:
        return ""


def _mongodb_client_kwargs(uri: str) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "serverSelectionTimeoutMS": _server_selection_timeout_ms(),
        "connectTimeoutMS": _connect_timeout_ms(),
        "socketTimeoutMS": _socket_timeout_ms(),
        "maxIdleTimeMS": _env_int("MONGO_MAX_IDLE_TIME_MS", 60000, min_value=1000, max_value=900000),
        "heartbeatFrequencyMS": _env_int("MONGO_HEARTBEAT_FREQUENCY_MS", 10000, min_value=500, max_value=60000),
        "retryWrites": _env_bool("MONGO_RETRY_WRITES", True),
        "retryReads": _env_bool("MONGO_RETRY_READS", True),
    }

    app_name = _clean_env_text(os.getenv("MONGO_APP_NAME", "SkylineBOT"))
    if app_name:
        kwargs["appname"] = app_name[:128]

    max_pool_size = _env_int("MONGO_MAX_POOL_SIZE", 100, min_value=1, max_value=1000)
    min_pool_size = _env_int("MONGO_MIN_POOL_SIZE", 0, min_value=0, max_value=max_pool_size)
    kwargs["maxPoolSize"] = max_pool_size
    kwargs["minPoolSize"] = min_pool_size

    direct_connection_raw = os.getenv("MONGO_DIRECT_CONNECTION")
    if direct_connection_raw is not None:
        kwargs["directConnection"] = _env_bool("MONGO_DIRECT_CONNECTION", False)

    tls_from_uri = _uri_declares_tls(uri)
    tls_from_env = os.getenv("MONGO_TLS")
    if tls_from_env is None:
        tls_enabled = bool(tls_from_uri) if tls_from_uri is not None else False
    else:
        tls_enabled = _env_bool("MONGO_TLS", bool(tls_from_uri) if tls_from_uri is not None else False)

    if tls_enabled:
        kwargs["tls"] = True
        ca_file = _clean_env_text(os.getenv("MONGO_TLS_CA_FILE", ""))
        if not ca_file and _env_bool("MONGO_TLS_USE_CERTIFI", True):
            ca_file = _default_tls_ca_file()
        if ca_file:
            kwargs["tlsCAFile"] = ca_file

        allow_invalid_certificates = _env_bool("MONGO_TLS_ALLOW_INVALID_CERTIFICATES", False)
        allow_invalid_hostnames = _env_bool("MONGO_TLS_ALLOW_INVALID_HOSTNAMES", False)
        if allow_invalid_certificates:
            kwargs["tlsAllowInvalidCertificates"] = True
        if allow_invalid_hostnames:
            kwargs["tlsAllowInvalidHostnames"] = True

    read_preference = _preferred_read_preference(uri)
    if read_preference:
        kwargs["readPreference"] = read_preference

    return kwargs


def mongo_build_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, **_mongodb_client_kwargs(uri))


def mongo_quota_error_text(error: Exception | str | None) -> str:
    return str(error or "").strip().lower()


def mongo_is_quota_or_capacity_error(error: Exception | str | None) -> bool:
    text = mongo_quota_error_text(error)
    if not text:
        return False
    tokens = (
        "quota",
        "over your space quota",
        "storage limit",
        "exceeded storage",
        "disk full",
        "allocation exceeded",
        "atlaserror",
        "8000",
    )
    return any(token in text for token in tokens)


def _mongo_multi_enabled() -> bool:
    return _env_bool("MONGO_MULTI_ENABLED", True)


def _mongo_primary_first_boot_enabled(uri_count: int, *, multi_enabled: bool) -> bool:
    if uri_count <= 1:
        return False
    if not multi_enabled:
        return False
    return _env_bool("MONGO_BOOT_PRIMARY_FIRST", False)


def _mongo_backup_warmup_enabled() -> bool:
    return _env_bool("MONGO_WARMUP_BACKUPS", True)


def _mongo_primary_first_fast_fail_enabled() -> bool:
    return _env_bool("MONGO_PRIMARY_FIRST_FAST_FAIL", True)


def _mongo_primary_first_probe_overrides() -> dict[str, int]:
    if not _mongo_primary_first_fast_fail_enabled():
        return {}

    default_selection = min(_server_selection_timeout_ms(), 2500)
    default_connect = min(_connect_timeout_ms(), 3500)
    default_socket = min(_socket_timeout_ms(), 3500)
    return {
        "serverSelectionTimeoutMS": _env_int(
            "MONGO_PRIMARY_FIRST_SERVER_SELECTION_TIMEOUT_MS",
            default_selection,
            min_value=500,
            max_value=30000,
        ),
        "connectTimeoutMS": _env_int(
            "MONGO_PRIMARY_FIRST_CONNECT_TIMEOUT_MS",
            default_connect,
            min_value=500,
            max_value=120000,
        ),
        "socketTimeoutMS": _env_int(
            "MONGO_PRIMARY_FIRST_SOCKET_TIMEOUT_MS",
            default_socket,
            min_value=500,
            max_value=120000,
        ),
    }


def mongo_normalize_read_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"primary", "aggregate"}:
        return mode
    return "aggregate"


def mongo_normalize_write_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"primary", "hash", "broadcast"}:
        return mode
    return "hash"


def _mongo_read_mode(uri_count: int) -> str:
    if uri_count <= 1:
        return "primary"
    return mongo_normalize_read_mode(_clean_env_text(os.getenv("MONGO_MULTI_READ_MODE", "aggregate")).lower())


def _mongo_write_mode(uri_count: int) -> str:
    if uri_count <= 1:
        return "primary"
    return mongo_normalize_write_mode(_clean_env_text(os.getenv("MONGO_MULTI_WRITE_MODE", "hash")).lower())


def mongo_current_read_mode() -> str:
    return _mongo_read_mode(len(_candidate_uris()))


def mongo_current_write_mode() -> str:
    return _mongo_write_mode(len(_candidate_uris()))


def _mongo_retryable_error_text(error: Exception | str | None) -> str:
    return str(error or "").strip().lower()


def _mongo_is_retryable_cluster_error(error: Exception | str | None) -> bool:
    if mongo_is_quota_or_capacity_error(error):
        return True
    text = _mongo_retryable_error_text(error)
    if not text:
        return False
    retry_tokens = (
        "connection refused",
        "connection reset",
        "econnreset",
        "broken pipe",
        "network timeout",
        "network error",
        "timed out",
        "server selection timeout",
        "serverselectiontimeout",
        "topology",
        "node is recovering",
        "not primary",
        "interrupted at shutdown",
        "shutdown in progress",
        "socket exception",
        "dns",
        "tls handshake",
    )
    return any(token in text for token in retry_tokens)


def mongo_is_transient_cluster_error(error: Exception | str | None) -> bool:
    return _mongo_is_retryable_cluster_error(error)


def _json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    except Exception:
        return str(value)


def _route_seed_from_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    route_keys = (
        "_id",
        "id",
        "guild_id",
        "user_id",
        "channel_id",
        "message_id",
        "code",
        "name",
        "scope",
    )
    for key in route_keys:
        value = payload.get(key)
        if key in payload and value is not None and value != "":
            return {key: payload.get(key)}

    for operator_name in ("$set", "$inc", "$setOnInsert", "$push", "$addToSet"):
        nested = payload.get(operator_name)
        if not isinstance(nested, dict):
            continue
        for key in route_keys:
            value = nested.get(key)
            if key in nested and value is not None and value != "":
                return {key: nested.get(key)}

    return payload


def _stable_hash_bucket(seed: Any, total: int) -> int:
    size = max(1, int(total))
    if size <= 1:
        return 0
    if seed is None or seed == {} or seed == "":
        return 0
    digest = hashlib.sha1(_json_dumps_safe(seed).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % size


def _ordered_by_hash(refs: list[Any], seed: Any) -> list[Any]:
    if len(refs) <= 1:
        return list(refs)
    start = _stable_hash_bucket(seed, len(refs))
    return [refs[(start + offset) % len(refs)] for offset in range(len(refs))]


def _extract_sort_spec(key_or_list: Any, direction: Any = None) -> list[tuple[str, int]]:
    if isinstance(key_or_list, (list, tuple)):
        if len(key_or_list) == 2 and not isinstance(key_or_list[0], (list, tuple)):
            pairs = [key_or_list]
        else:
            pairs = list(key_or_list)
    else:
        pairs = [(key_or_list, direction if direction is not None else 1)]

    sort_spec: list[tuple[str, int]] = []
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        field = str(pair[0] or "").strip()
        if not field:
            continue
        try:
            direction_int = int(pair[1])
        except Exception:
            direction_int = 1
        sort_spec.append((field, -1 if direction_int < 0 else 1))
    return sort_spec


def _dot_lookup(document: Any, dotted_key: str) -> Any:
    if not isinstance(document, dict):
        return None
    current: Any = document
    for segment in str(dotted_key or "").split("."):
        if not isinstance(current, dict):
            return None
        if segment not in current:
            return None
        current = current.get(segment)
    return current


def _sortable_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, "")
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        return (2, float(value))
    if hasattr(value, "timestamp"):
        try:
            return (3, float(value.timestamp()))
        except Exception:
            pass
    if isinstance(value, str):
        return (4, value.lower())
    return (5, _json_dumps_safe(value))


def _compare_documents(left: Any, right: Any, sort_spec: list[tuple[str, int]]) -> int:
    left_doc = left if isinstance(left, dict) else {}
    right_doc = right if isinstance(right, dict) else {}
    for field_name, direction in sort_spec:
        left_value = _sortable_value(_dot_lookup(left_doc, field_name))
        right_value = _sortable_value(_dot_lookup(right_doc, field_name))
        if left_value < right_value:
            return -1 if direction >= 0 else 1
        if left_value > right_value:
            return 1 if direction >= 0 else -1
    return 0


def _document_identity(document: Any) -> str:
    if not isinstance(document, dict):
        return f"raw:{_json_dumps_safe(document)}"
    for key in ("_id", "id"):
        value = document.get(key)
        if value is not None and value != "":
            return f"{key}:{value}"
    return f"hash:{hashlib.sha1(_json_dumps_safe(document).encode('utf-8')).hexdigest()}"


def _dedupe_documents(rows: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for row in rows:
        identity = _document_identity(row)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(row)
    return deduped


class _MongoCursorProxy:
    def __init__(
        self,
        refs: list[tuple[str, Any]],
        query: Any,
        projection: Any,
        find_args: tuple[Any, ...],
        find_kwargs: dict[str, Any],
        *,
        aggregate_mode: bool,
    ) -> None:
        self._refs = list(refs)
        self._query = query if query is not None else {}
        self._projection = projection
        self._find_args = tuple(find_args or ())
        self._find_kwargs = dict(find_kwargs or {})
        self._aggregate_mode = bool(aggregate_mode and len(self._refs) > 1)
        self._sort_spec: list[tuple[str, int]] = []
        self._skip_count = 0
        self._limit_count: int | None = None

    def sort(self, key_or_list: Any, direction: Any = None):
        self._sort_spec = _extract_sort_spec(key_or_list, direction)
        return self

    def skip(self, value: Any):
        try:
            parsed = int(value)
        except Exception:
            parsed = 0
        self._skip_count = max(0, parsed)
        return self

    def limit(self, value: Any):
        try:
            parsed = int(value)
        except Exception:
            parsed = 0
        self._limit_count = parsed if parsed > 0 else None
        return self

    async def _fetch_collection_rows(self, uri: str, collection: Any, *, fetch_limit: int | None) -> list[Any]:
        try:
            cursor = collection.find(self._query, self._projection, *self._find_args, **self._find_kwargs)
            if self._sort_spec:
                cursor = cursor.sort(self._sort_spec)
            if fetch_limit is not None:
                cursor = cursor.limit(fetch_limit)
            rows = await cursor.to_list(length=fetch_limit)
            _record_cluster_io(uri, io_kind="read", ok=True)
            return rows
        except Exception as error:
            _record_cluster_io(uri, io_kind="read", ok=False, error=error)
            raise

    async def _to_list_primary(self, requested_length: int | None) -> list[Any]:
        uri, collection = self._refs[0]
        try:
            cursor = collection.find(self._query, self._projection, *self._find_args, **self._find_kwargs)
            if self._sort_spec:
                cursor = cursor.sort(self._sort_spec)
            if self._skip_count > 0:
                cursor = cursor.skip(self._skip_count)
            if self._limit_count is not None:
                cursor = cursor.limit(self._limit_count)

            if requested_length is not None and self._limit_count is not None:
                rows = await cursor.to_list(length=min(requested_length, self._limit_count))
            elif requested_length is not None:
                rows = await cursor.to_list(length=requested_length)
            else:
                rows = await cursor.to_list(length=None)
            _record_cluster_io(uri, io_kind="read", ok=True)
            return rows
        except Exception as error:
            _record_cluster_io(uri, io_kind="read", ok=False, error=error)
            raise

    async def to_list(self, *, length: int | None):
        requested_length = None if length is None else max(0, int(length))
        if not self._refs:
            return []
        if not self._aggregate_mode:
            return await self._to_list_primary(requested_length)

        effective_limit = self._limit_count
        if requested_length is not None:
            if effective_limit is None:
                effective_limit = requested_length
            else:
                effective_limit = min(effective_limit, requested_length)

        fetch_limit: int | None = None
        if effective_limit is not None:
            fetch_limit = max(0, self._skip_count + effective_limit)
        elif self._skip_count > 0:
            fetch_limit = max(
                1,
                self._skip_count + _env_int("MONGO_MULTI_CURSOR_PREFETCH", 5000, min_value=100, max_value=50000),
            )

        tasks = [
            self._fetch_collection_rows(uri, collection, fetch_limit=fetch_limit)
            for (uri, collection) in self._refs
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        rows: list[Any] = []
        errors: list[Exception] = []
        for item in gathered:
            if isinstance(item, Exception):
                errors.append(item)
                continue
            rows.extend(list(item or []))

        if not rows and errors:
            raise errors[0]
        if errors:
            logger.warning(f"Mongo multi-read partial failure: {errors[0]}")

        rows = _dedupe_documents(rows)
        if self._sort_spec:
            rows.sort(key=cmp_to_key(lambda left, right: _compare_documents(left, right, self._sort_spec)))

        if self._skip_count > 0:
            rows = rows[self._skip_count :]
        if effective_limit is not None:
            rows = rows[: max(0, effective_limit)]
        if requested_length is not None:
            rows = rows[:requested_length]
        return rows

    def __aiter__(self):
        return _MongoCursorProxyIterator(self)


class _MongoCursorProxyIterator:
    def __init__(self, cursor_proxy: _MongoCursorProxy) -> None:
        self._cursor_proxy = cursor_proxy
        self._rows: list[Any] | None = None
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._rows is None:
            self._rows = await self._cursor_proxy.to_list(length=None)
        if self._index >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._index]
        self._index += 1
        return row


class _MongoCollectionProxy:
    def __init__(
        self,
        name: str,
        refs: list[tuple[str, Any]],
        *,
        read_mode: str,
        write_mode: str,
        ordered_routing: bool,
        database_proxy: "_MongoDatabaseProxy",
    ) -> None:
        self.name = name
        self._refs = list(refs)
        self._read_mode = str(read_mode or "primary")
        self._write_mode = str(write_mode or "primary")
        self._ordered_routing = bool(ordered_routing)
        self.database = database_proxy

    def _aggregate_read_enabled(self) -> bool:
        return self._read_mode == "aggregate" and len(self._refs) > 1

    def _ordered_refs(self, seed: Any) -> list[tuple[str, Any]]:
        if self._ordered_routing:
            return list(self._refs)
        return _ordered_by_hash(self._refs, seed)

    def _read_refs(self, seed: Any) -> list[tuple[str, Any]]:
        ordered = self._ordered_refs(seed)
        if self._aggregate_read_enabled():
            return ordered
        return ordered[:1]

    def _write_refs(self, seed: Any) -> list[tuple[str, Any]]:
        ordered = self._ordered_refs(seed)
        if self._write_mode == "broadcast" and len(ordered) > 1:
            return ordered
        if self._write_mode == "primary":
            return ordered[:1]
        return ordered

    def _primary_collection(self) -> Any:
        return self._refs[0][1]

    def _should_failover_write(self, error: Exception) -> bool:
        return _mongo_is_retryable_cluster_error(error)

    def find(self, *args, **kwargs):
        find_kwargs = dict(kwargs or {})
        if args:
            query = args[0]
            find_kwargs.pop("filter", None)
        else:
            query = find_kwargs.pop("filter", None)
        if query is None:
            query = {}

        projection = None
        if len(args) >= 2:
            projection = args[1]
            find_kwargs.pop("projection", None)
        else:
            projection = find_kwargs.pop("projection", None)

        if len(args) >= 2:
            find_args = tuple(args[2:])
        elif len(args) == 1:
            find_args = tuple(args[1:])
        else:
            find_args = tuple()

        refs = self._read_refs(_route_seed_from_payload(query))
        return _MongoCursorProxy(
            refs,
            query,
            projection,
            find_args,
            find_kwargs,
            aggregate_mode=self._aggregate_read_enabled(),
        )

    async def find_one(self, filter: Any = None, *args, **kwargs):
        query = filter if filter is not None else {}
        find_one_kwargs = dict(kwargs or {})
        if args:
            projection = args[0]
            extra_args = tuple(args[1:])
            find_one_kwargs.pop("projection", None)
        else:
            projection = find_one_kwargs.pop("projection", None)
            extra_args = tuple()

        sort_value = find_one_kwargs.get("sort")
        if self._aggregate_read_enabled() and sort_value is not None:
            cursor = self.find(query, projection)
            if sort_value is not None:
                cursor = cursor.sort(sort_value)
            skip_value = find_one_kwargs.get("skip")
            if skip_value is not None:
                cursor = cursor.skip(skip_value)
            rows = await cursor.limit(1).to_list(length=1)
            return rows[0] if rows else None

        errors: list[Exception] = []
        for uri, collection in self._read_refs(_route_seed_from_payload(query)):
            try:
                if projection is None:
                    row = await collection.find_one(query, *extra_args, **find_one_kwargs)
                else:
                    row = await collection.find_one(query, projection, *extra_args, **find_one_kwargs)
                _record_cluster_io(uri, io_kind="read", ok=True)
                if row is not None:
                    return row
            except Exception as error:
                errors.append(error)
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                if not self._aggregate_read_enabled():
                    raise
        if errors and len(errors) == len(self._read_refs(_route_seed_from_payload(query))):
            raise errors[0]
        return None

    async def count_documents(self, filter: Any = None, *args, **kwargs) -> int:
        query = filter if filter is not None else {}
        refs = self._read_refs(_route_seed_from_payload(query))
        if len(refs) <= 1 or not self._aggregate_read_enabled():
            uri, collection = refs[0]
            try:
                value = int(await collection.count_documents(query, *args, **kwargs))
                _record_cluster_io(uri, io_kind="read", ok=True)
                return value
            except Exception as error:
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                raise

        async def _count_for(uri: str, collection: Any) -> int:
            try:
                value = int(await collection.count_documents(query, *args, **kwargs))
                _record_cluster_io(uri, io_kind="read", ok=True)
                return value
            except Exception as error:
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                raise

        tasks = [_count_for(uri, collection) for (uri, collection) in refs]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        total = 0
        errors: list[Exception] = []
        for item in gathered:
            if isinstance(item, Exception):
                errors.append(item)
                continue
            total += int(item or 0)
        if total <= 0 and errors:
            raise errors[0]
        if errors:
            logger.warning(f"Mongo multi-count partial failure: {errors[0]}")
        return int(total)

    async def estimated_document_count(self, *args, **kwargs) -> int:
        if len(self._refs) <= 1 or not self._aggregate_read_enabled():
            uri, collection = self._refs[0]
            try:
                value = int(await collection.estimated_document_count(*args, **kwargs))
                _record_cluster_io(uri, io_kind="read", ok=True)
                return value
            except Exception as error:
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                raise

        async def _estimate_for(uri: str, collection: Any) -> int:
            try:
                value = int(await collection.estimated_document_count(*args, **kwargs))
                _record_cluster_io(uri, io_kind="read", ok=True)
                return value
            except Exception as error:
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                raise

        tasks = [_estimate_for(uri, collection) for (uri, collection) in self._refs]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        total = 0
        errors: list[Exception] = []
        for item in gathered:
            if isinstance(item, Exception):
                errors.append(item)
                continue
            total += int(item or 0)
        if total <= 0 and errors:
            raise errors[0]
        if errors:
            logger.warning(f"Mongo multi-estimated count partial failure: {errors[0]}")
        return int(total)

    async def insert_one(self, document: Any, *args, **kwargs):
        refs = self._write_refs(_route_seed_from_payload(document))
        if len(refs) <= 1:
            uri, collection = refs[0]
            try:
                result = await collection.insert_one(document, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise

        if self._write_mode == "broadcast":
            first_result = None
            errors: list[Exception] = []
            for uri, collection in refs:
                try:
                    result = await collection.insert_one(document, *args, **kwargs)
                    _record_cluster_io(uri, io_kind="write", ok=True)
                    if first_result is None:
                        first_result = result
                except Exception as error:
                    errors.append(error)
                    _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                    logger.warning(f"Mongo broadcast insert failed on {_mask_uri_host(uri)}: {error}")
            if first_result is not None:
                return first_result
            if errors:
                raise errors[0]
            raise RuntimeError("Mongo broadcast insert failed on all clusters")

        last_error: Exception | None = None
        for index, (uri, collection) in enumerate(refs):
            try:
                result = await collection.insert_one(document, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                if index < len(refs) - 1 and self._should_failover_write(error):
                    logger.warning(
                        f"Mongo write failover insert {self.name}: {_mask_uri_host(uri)} -> next cluster ({error})"
                    )
                    continue
                raise
        raise RuntimeError(f"Mongo insert failed on all clusters for {self.name}: {last_error}") from last_error

    async def update_one(self, filter: Any, update: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        refs = self._write_refs(_route_seed_from_payload(query))
        upsert_enabled = bool(kwargs.get("upsert"))

        if len(refs) <= 1:
            uri, collection = refs[0]
            try:
                result = await collection.update_one(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise

        if self._write_mode == "broadcast":
            matched = 0
            modified = 0
            upserted_id = None
            success_count = 0
            errors: list[Exception] = []
            for uri, collection in refs:
                try:
                    result = await collection.update_one(query, update, *args, **kwargs)
                    _record_cluster_io(uri, io_kind="write", ok=True)
                    success_count += 1
                    matched += int(getattr(result, "matched_count", 0) or 0)
                    modified += int(getattr(result, "modified_count", 0) or 0)
                    if upserted_id is None and getattr(result, "upserted_id", None) is not None:
                        upserted_id = getattr(result, "upserted_id", None)
                except Exception as error:
                    errors.append(error)
                    _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                    logger.warning(f"Mongo broadcast update failed on {_mask_uri_host(uri)}: {error}")
            if success_count <= 0 and errors:
                raise errors[0]
            return SimpleNamespace(
                matched_count=int(matched),
                modified_count=int(modified),
                upserted_id=upserted_id,
                acknowledged=bool(success_count > 0),
            )

        last_error: Exception | None = None
        for index, (uri, collection) in enumerate(refs):
            try:
                result = await collection.update_one(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                matched = int(getattr(result, "matched_count", 0) or 0)
                modified = int(getattr(result, "modified_count", 0) or 0)
                upserted_id = getattr(result, "upserted_id", None)
                if matched > 0 or modified > 0 or upserted_id is not None:
                    return result
                if upsert_enabled:
                    return result
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                if index < len(refs) - 1 and self._should_failover_write(error):
                    logger.warning(
                        f"Mongo write failover update {self.name}: {_mask_uri_host(uri)} -> next cluster ({error})"
                    )
                    continue
                raise

        if last_error is not None and upsert_enabled:
            raise last_error
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None, acknowledged=True)

    async def update_many(self, filter: Any, update: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        refs = self._write_refs(_route_seed_from_payload(query))
        if len(refs) <= 1:
            uri, collection = refs[0]
            try:
                result = await collection.update_many(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise
        matched = 0
        modified = 0
        upserted_id = None
        success_count = 0
        errors: list[Exception] = []
        for uri, collection in refs:
            try:
                result = await collection.update_many(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                success_count += 1
                matched += int(getattr(result, "matched_count", 0) or 0)
                modified += int(getattr(result, "modified_count", 0) or 0)
                if upserted_id is None and getattr(result, "upserted_id", None) is not None:
                    upserted_id = getattr(result, "upserted_id", None)
            except Exception as error:
                errors.append(error)
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                logger.warning(f"Mongo multi update_many failed on {_mask_uri_host(uri)}: {error}")
        if success_count <= 0 and errors:
            raise errors[0]
        return SimpleNamespace(
            matched_count=int(matched),
            modified_count=int(modified),
            upserted_id=upserted_id,
            acknowledged=bool(success_count > 0),
        )

    async def find_one_and_update(self, filter: Any, update: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        refs = self._write_refs(_route_seed_from_payload(query))
        upsert_enabled = bool(kwargs.get("upsert"))

        if len(refs) <= 1:
            uri, collection = refs[0]
            try:
                row = await collection.find_one_and_update(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return row
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise

        last_error: Exception | None = None
        for index, (uri, collection) in enumerate(refs):
            try:
                row = await collection.find_one_and_update(query, update, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                if row is not None:
                    return row
                if upsert_enabled:
                    return row
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                if index < len(refs) - 1 and self._should_failover_write(error):
                    logger.warning(
                        f"Mongo write failover find_one_and_update {self.name}: "
                        f"{_mask_uri_host(uri)} -> next cluster ({error})"
                    )
                    continue
                raise
        if upsert_enabled and last_error is not None:
            raise last_error
        return None

    async def replace_one(self, filter: Any, replacement: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        refs = self._write_refs(_route_seed_from_payload(query))
        if len(refs) <= 1:
            uri, collection = refs[0]
            try:
                result = await collection.replace_one(query, replacement, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise
        last_error: Exception | None = None
        for index, (uri, collection) in enumerate(refs):
            try:
                result = await collection.replace_one(query, replacement, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                matched = int(getattr(result, "matched_count", 0) or 0)
                modified = int(getattr(result, "modified_count", 0) or 0)
                upserted_id = getattr(result, "upserted_id", None)
                if matched > 0 or modified > 0 or upserted_id is not None or bool(kwargs.get("upsert")):
                    return result
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                if index < len(refs) - 1 and self._should_failover_write(error):
                    continue
                raise
        if last_error is not None and bool(kwargs.get("upsert")):
            raise last_error
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None, acknowledged=True)

    async def delete_many(self, filter: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        if len(self._refs) <= 1:
            uri, collection = self._refs[0]
            try:
                result = await collection.delete_many(query, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise

        deleted_total = 0
        success_count = 0
        errors: list[Exception] = []
        for uri, collection in self._refs:
            try:
                result = await collection.delete_many(query, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                deleted_total += int(getattr(result, "deleted_count", 0) or 0)
                success_count += 1
            except Exception as error:
                errors.append(error)
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                logger.warning(f"Mongo multi delete_many failed on {_mask_uri_host(uri)}: {error}")
        if success_count <= 0 and errors:
            raise errors[0]
        return SimpleNamespace(deleted_count=int(deleted_total), acknowledged=bool(success_count > 0))

    async def delete_one(self, filter: Any, *args, **kwargs):
        query = filter if filter is not None else {}
        if len(self._refs) <= 1:
            uri, collection = self._refs[0]
            try:
                result = await collection.delete_one(query, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return result
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise
        deleted_total = 0
        success_count = 0
        errors: list[Exception] = []
        for uri, collection in self._refs:
            try:
                result = await collection.delete_one(query, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                deleted_total += int(getattr(result, "deleted_count", 0) or 0)
                success_count += 1
            except Exception as error:
                errors.append(error)
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                logger.warning(f"Mongo multi delete_one failed on {_mask_uri_host(uri)}: {error}")
        if success_count <= 0 and errors:
            raise errors[0]
        return SimpleNamespace(deleted_count=int(deleted_total), acknowledged=bool(success_count > 0))

    async def create_index(self, keys: Any, *args, **kwargs):
        if len(self._refs) <= 1:
            uri, collection = self._refs[0]
            try:
                name = await collection.create_index(keys, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return name
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise
        first_name = ""
        success_count = 0
        last_error: Exception | None = None
        for uri, collection in self._refs:
            try:
                name = await collection.create_index(keys, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                if not first_name:
                    first_name = str(name or kwargs.get("name") or "")
                success_count += 1
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                logger.warning(f"Mongo multi create_index failed on {_mask_uri_host(uri)}: {error}")
        if success_count <= 0 and last_error is not None:
            raise last_error
        return first_name or str(kwargs.get("name") or "")

    async def index_information(self, *args, **kwargs):
        if len(self._refs) <= 1 or not self._aggregate_read_enabled():
            uri, collection = self._refs[0]
            try:
                info = await collection.index_information(*args, **kwargs)
                _record_cluster_io(uri, io_kind="read", ok=True)
                return info
            except Exception as error:
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
                raise
        merged: dict[str, Any] = {}
        errors: list[Exception] = []
        for uri, collection in self._refs:
            try:
                info = await collection.index_information(*args, **kwargs)
                _record_cluster_io(uri, io_kind="read", ok=True)
                for key, payload in dict(info or {}).items():
                    if key not in merged:
                        merged[str(key)] = payload
            except Exception as error:
                errors.append(error)
                _record_cluster_io(uri, io_kind="read", ok=False, error=error)
        if not merged and errors:
            raise errors[0]
        if errors:
            logger.warning(f"Mongo multi index_information partial failure: {errors[0]}")
        return merged

    async def drop_index(self, name: str, *args, **kwargs):
        if len(self._refs) <= 1:
            uri, collection = self._refs[0]
            try:
                value = await collection.drop_index(name, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                return value
            except Exception as error:
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                raise
        success_count = 0
        last_error: Exception | None = None
        for uri, collection in self._refs:
            try:
                await collection.drop_index(name, *args, **kwargs)
                _record_cluster_io(uri, io_kind="write", ok=True)
                success_count += 1
            except Exception as error:
                last_error = error
                _record_cluster_io(uri, io_kind="write", ok=False, error=error)
                text = _mongo_retryable_error_text(error)
                if "indexnotfound" in text or "not found" in text:
                    continue
                logger.warning(f"Mongo multi drop_index failed on {_mask_uri_host(uri)}: {error}")
        if success_count <= 0 and last_error is not None:
            raise last_error
        return None

    def __getattr__(self, item: str) -> Any:
        return getattr(self._primary_collection(), item)


class _MongoDatabaseProxy:
    def __init__(
        self,
        name: str,
        refs: list[tuple[str, Any, AsyncIOMotorClient]],
        *,
        read_mode: str,
        write_mode: str,
    ) -> None:
        self.name = str(name or "")
        self._refs = list(refs)
        self._read_mode = str(read_mode or "primary")
        self._write_mode = str(write_mode or "primary")
        self.client = self._refs[0][2]
        self._collection_cache: dict[str, _MongoCollectionProxy] = {}

    def _primary_database(self) -> Any:
        return self._refs[0][1]

    def __getitem__(self, collection_name: str):
        key = str(collection_name or "").strip()
        if not key:
            raise KeyError("Collection name is required")
        cached = self._collection_cache.get(key)
        if cached is not None:
            return cached
        routed_db_refs, ordered_routing = _route_collection_refs(key, self._refs)
        refs = [(uri, database[key]) for (uri, database, _client) in routed_db_refs]
        collection_proxy = _MongoCollectionProxy(
            key,
            refs,
            read_mode=self._read_mode,
            write_mode=self._write_mode,
            ordered_routing=ordered_routing,
            database_proxy=self,
        )
        self._collection_cache[key] = collection_proxy
        return collection_proxy

    async def list_collection_names(self, *args, **kwargs):
        if len(self._refs) <= 1 or self._read_mode != "aggregate":
            return await self._primary_database().list_collection_names(*args, **kwargs)
        rows: set[str] = set()
        errors: list[Exception] = []
        for _uri, database, _client in self._refs:
            try:
                names = await database.list_collection_names(*args, **kwargs)
                for name in names or []:
                    text = str(name or "").strip()
                    if text:
                        rows.add(text)
            except Exception as error:
                errors.append(error)
        if not rows and errors:
            raise errors[0]
        if errors:
            logger.warning(f"Mongo multi list_collection_names partial failure: {errors[0]}")
        return sorted(rows)

    async def command(self, *args, **kwargs):
        return await self._primary_database().command(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._primary_database(), item)


async def mongo_uri_diagnostics(
    uri: str,
    *,
    timeout_seconds: float = 4.0,
    max_collections: int = 80,
) -> dict[str, object]:
    safe_uri = _clean_env_text(uri or "")
    started = time.perf_counter()
    payload: dict[str, object] = {
        "ok": False,
        "uri": safe_uri,
        "host": _mask_uri_host(safe_uri),
        "database": mongo_database_name(),
        "latency_ms": 0,
        "detail": "",
        "collections_total": 0,
        "estimated_documents_total": 0,
        "storage_size_bytes": 0,
        "data_size_bytes": 0,
        "collection_rows": [],
        "quota_warning": False,
        "diagnostic_partial": False,
    }
    client: AsyncIOMotorClient | None = None
    try:
        client = mongo_build_client(safe_uri)
        ping_started = time.perf_counter()
        await asyncio.wait_for(client.admin.command("ping"), timeout=max(1.0, float(timeout_seconds)))
        payload["latency_ms"] = int((time.perf_counter() - ping_started) * 1000)
        payload["ok"] = True
        payload["detail"] = "connected"

        database = client[mongo_database_name()]
        metrics_errors: list[str] = []
        db_stats: dict[str, object] = {}
        collection_names: list[str] = []
        metrics_timeout = max(1.0, float(timeout_seconds))
        metrics_results = await asyncio.gather(
            asyncio.wait_for(database.command("dbStats"), timeout=metrics_timeout),
            asyncio.wait_for(database.list_collection_names(), timeout=metrics_timeout),
            return_exceptions=True,
        )
        db_stats_result, collection_names_result = metrics_results
        if isinstance(db_stats_result, Exception):
            metrics_errors.append(f"dbStats: {type(db_stats_result).__name__}")
        else:
            db_stats = dict(db_stats_result or {})
        if isinstance(collection_names_result, Exception):
            metrics_errors.append(f"listCollections: {type(collection_names_result).__name__}")
        else:
            collection_names = [
                str(name or "").strip()
                for name in list(collection_names_result or [])
                if str(name or "").strip()
            ]

        limited_names = list(sorted(collection_names))[: max(1, int(max_collections))]
        rows: list[dict[str, object]] = []
        estimated_total = 0
        for name in limited_names:
            try:
                count_value = int(
                    await asyncio.wait_for(
                        database[name].estimated_document_count(),
                        timeout=min(1.2, max(0.25, float(timeout_seconds) / 6.0)),
                    )
                )
            except Exception:
                count_value = -1
            if count_value >= 0:
                estimated_total += count_value
            rows.append(
                {
                    "name": name,
                    "estimated_count": count_value,
                }
            )
        rows.sort(
            key=lambda item: int(item.get("estimated_count") or -1),
            reverse=True,
        )
        payload["collections_total"] = int(len(collection_names))
        payload["estimated_documents_total"] = int(estimated_total)
        payload["storage_size_bytes"] = int(db_stats.get("storageSize") or 0)
        payload["data_size_bytes"] = int(db_stats.get("dataSize") or 0)
        payload["collection_rows"] = rows
        if metrics_errors:
            payload["diagnostic_partial"] = True
            payload["detail"] = "connected (partial diagnostics: " + ", ".join(metrics_errors[:2]) + ")"
    except Exception as error:
        payload["ok"] = False
        payload["detail"] = f"{type(error).__name__}: {error}"
        payload["quota_warning"] = mongo_is_quota_or_capacity_error(error)
    finally:
        if int(payload.get("latency_ms") or 0) <= 0:
            payload["latency_ms"] = int((time.perf_counter() - started) * 1000)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    return payload


async def _probe_cluster_candidate(
    idx: int,
    uri: str,
    semaphore: asyncio.Semaphore,
    *,
    overrides: dict[str, int] | None = None,
) -> tuple[int, str, AsyncIOMotorClient | None, dict[str, object], Exception | None]:
    if _looks_placeholder_uri(uri):
        placeholder_error = RuntimeError(
            "MONGO_URI still uses placeholder host 'cluster.mongodb.net'. Replace with real host."
        )
        return int(idx), uri, None, {}, placeholder_error

    async with semaphore:
        candidate_kwargs = _mongodb_client_kwargs(uri)
        if overrides:
            candidate_kwargs.update(
                {str(key): int(value) for key, value in dict(overrides or {}).items() if value is not None}
            )
        candidate = AsyncIOMotorClient(uri, **candidate_kwargs)
        try:
            await candidate.admin.command("ping")
            return int(idx), uri, candidate, candidate_kwargs, None
        except Exception as error:
            try:
                candidate.close()
            except Exception:
                pass
            return int(idx), uri, None, candidate_kwargs, error


def _on_backup_warmup_done(task: asyncio.Task[None]) -> None:
    global _backup_warmup_task
    if _backup_warmup_task is task:
        _backup_warmup_task = None
    if task.cancelled():
        return
    try:
        error = task.exception()
    except Exception as callback_error:
        logger.warning(f"MongoDB backup warm-up callback failed: {callback_error}")
        return
    if error is not None:
        logger.warning(f"MongoDB backup warm-up failed: {error}")


def _start_backup_warmup(candidate_uris: list[str]) -> None:
    global _backup_warmup_task
    if not _mongo_backup_warmup_enabled():
        return
    if len(candidate_uris) <= 1:
        return
    existing_task = _backup_warmup_task
    if existing_task is not None and not existing_task.done():
        return
    task = asyncio.create_task(_warmup_backup_clusters(list(candidate_uris)))
    _backup_warmup_task = task
    task.add_done_callback(_on_backup_warmup_done)


async def _warmup_backup_clusters(candidate_uris: list[str]) -> None:
    global _client, _database, _cluster_clients, _cluster_databases, _cluster_databases_key, _database_key
    if not _mongo_multi_enabled():
        return
    uris = list(candidate_uris or _candidate_uris())
    if len(uris) <= 1:
        return

    existing_snapshot = list(_cluster_clients or [])
    existing_uris = {uri for uri, _client_ref in existing_snapshot}
    probe_targets = [
        (idx, uri)
        for idx, uri in enumerate(uris, start=1)
        if idx > 1 and uri not in existing_uris
    ]
    if not probe_targets:
        return

    max_parallel = _env_int("MONGO_WARMUP_PARALLELISM", 0, min_value=0, max_value=64)
    if max_parallel <= 0:
        max_parallel = len(probe_targets)
    semaphore = asyncio.Semaphore(max(1, min(max_parallel, len(probe_targets))))

    probe_tasks = [
        asyncio.create_task(_probe_cluster_candidate(idx, uri, semaphore))
        for idx, uri in probe_targets
    ]
    probe_results = await asyncio.gather(*probe_tasks)
    probe_results.sort(key=lambda row: int(row[0]))

    added_clients: list[tuple[int, str, AsyncIOMotorClient]] = []
    failed_candidates: list[tuple[int, str, str]] = []
    for idx, uri, candidate, _candidate_kwargs, error in probe_results:
        if error is None and candidate is not None:
            added_clients.append((int(idx), uri, candidate))
            continue
        if error is not None:
            failed_candidates.append(
                (
                    int(idx),
                    _mask_uri_host(uri),
                    f"{type(error).__name__}: {str(error)[:260]}",
                )
            )

    if not added_clients:
        if failed_candidates:
            failed_summary = ", ".join(
                [f"#{idx}:{host}" for idx, host, _detail in failed_candidates[:6]]
            )
            logger.info(f"MongoDB backup warm-up unavailable: {failed_summary}")
        return

    async with _connect_clients_lock:
        previous_count = len(_cluster_clients or [])
        current_map: dict[str, AsyncIOMotorClient] = {
            uri: client for uri, client in list(_cluster_clients or [])
        }
        for _idx, uri, candidate in added_clients:
            existing_client = current_map.get(uri)
            if existing_client is None:
                current_map[uri] = candidate
                continue
            try:
                candidate.close()
            except Exception:
                pass

        merged_clients: list[tuple[str, AsyncIOMotorClient]] = []
        for uri in uris:
            client = current_map.get(uri)
            if client is not None:
                merged_clients.append((uri, client))

        if not merged_clients:
            return

        _cluster_clients = list(merged_clients)
        _client = merged_clients[0][1]
        if len(merged_clients) != previous_count:
            _cluster_databases = None
            _cluster_databases_key = None
            _database = None
            _database_key = None

    logger.info(
        "MongoDB backup warm-up ready: "
        f"added {len(added_clients)} cluster(s), active {len(_cluster_clients or [])}/{len(uris)}"
    )
    for idx, uri, _candidate in added_clients[:3]:
        logger.debug(
            f"MongoDB backup warm-up connected (candidate {idx}, host={_mask_uri_host(uri)})"
        )
    for failed_idx, failed_host, failed_detail in failed_candidates[:3]:
        logger.debug(
            f"MongoDB backup warm-up unavailable (candidate {failed_idx}: {failed_host}) | {failed_detail}"
        )


async def _connect_cluster_clients_impl() -> list[tuple[str, AsyncIOMotorClient]]:
    global _client, _database, _cluster_clients, _cluster_databases, _cluster_databases_key, _database_key, _last_connect_error, _last_connect_error_at
    if _cluster_clients:
        return list(_cluster_clients)

    cooldown_seconds = _retry_cooldown_seconds()
    if _last_connect_error is not None and cooldown_seconds > 0:
        elapsed = max(0.0, time.monotonic() - float(_last_connect_error_at or 0.0))
        if elapsed < cooldown_seconds:
            remaining = max(0.0, cooldown_seconds - elapsed)
            raise RuntimeError(
                f"MongoDB connect cooldown active ({remaining:.1f}s remaining). "
                f"Last error: {_last_connect_error}"
            ) from _last_connect_error

    uris = _candidate_uris()
    if not uris:
        raise RuntimeError("MONGO_URI is empty. Set a valid MongoDB URI in .env")

    multi_enabled = _mongo_multi_enabled()
    timeout_ms = _server_selection_timeout_ms()
    primary_first_enabled = _mongo_primary_first_boot_enabled(len(uris), multi_enabled=multi_enabled)
    primary_probe_result: tuple[int, str, AsyncIOMotorClient | None, dict[str, object], Exception | None] | None = None

    if primary_first_enabled:
        primary_overrides = _mongo_primary_first_probe_overrides()
        primary_probe_result = await _probe_cluster_candidate(
            1,
            uris[0],
            asyncio.Semaphore(1),
            overrides=primary_overrides,
        )
        idx, uri, candidate, candidate_kwargs, error = primary_probe_result
        if error is None and candidate is not None:
            tls_info = "tls=on" if bool(candidate_kwargs.get("tls")) else "tls=auto-or-off"
            runtime_client = candidate
            runtime_kwargs = _mongodb_client_kwargs(uri)
            runtime_connect_ms = int(runtime_kwargs.get("connectTimeoutMS") or 0)
            runtime_socket_ms = int(runtime_kwargs.get("socketTimeoutMS") or 0)
            probe_connect_ms = int(candidate_kwargs.get("connectTimeoutMS") or 0)
            probe_socket_ms = int(candidate_kwargs.get("socketTimeoutMS") or 0)
            if (
                runtime_connect_ms > 0
                and runtime_socket_ms > 0
                and (
                    probe_connect_ms < runtime_connect_ms
                    or probe_socket_ms < runtime_socket_ms
                )
            ):
                try:
                    upgraded_client = mongo_build_client(uri)
                    await upgraded_client.admin.command("ping")
                    runtime_client = upgraded_client
                    try:
                        candidate.close()
                    except Exception:
                        pass
                    logger.info(
                        "MongoDB primary-first runtime client upgraded "
                        f"(host={_mask_uri_host(uri)}, connectTimeoutMS={runtime_connect_ms}, "
                        f"socketTimeoutMS={runtime_socket_ms})"
                    )
                except Exception as upgrade_error:
                    logger.warning(
                        "MongoDB primary-first runtime client upgrade failed; using probe timeouts "
                        f"(host={_mask_uri_host(uri)}): {type(upgrade_error).__name__}: {upgrade_error}"
                    )
            logger.info(
                f"MongoDB connected (candidate {idx}, host={_mask_uri_host(uri)}, {tls_info}, "
                f"serverSelectionTimeoutMS={candidate_kwargs.get('serverSelectionTimeoutMS')}, mode=primary-first)"
            )
            _cluster_clients = [(uri, runtime_client)]
            _client = runtime_client
            _cluster_databases = None
            _cluster_databases_key = None
            _database = None
            _database_key = None
            _last_connect_error = None
            _last_connect_error_at = 0.0
            _start_backup_warmup(uris)
            return list(_cluster_clients)
        if error is not None:
            logger.warning(
                "MongoDB primary-first bootstrap failed "
                f"(candidate {idx}: {_mask_uri_host(uri)}): {type(error).__name__}: {str(error)[:220]} "
                f"| falling back to full candidate probe (primary connectTimeoutMS="
                f"{candidate_kwargs.get('connectTimeoutMS')}, socketTimeoutMS={candidate_kwargs.get('socketTimeoutMS')})"
            )

    max_parallel = _env_int("MONGO_CONNECT_PARALLELISM", 0, min_value=0, max_value=64)
    if max_parallel <= 0:
        max_parallel = len(uris)
    semaphore = asyncio.Semaphore(max(1, min(max_parallel, len(uris))))

    probe_results: list[tuple[int, str, AsyncIOMotorClient | None, dict[str, object], Exception | None]] = []
    start_index = 1
    if primary_probe_result is not None:
        probe_results.append(primary_probe_result)
        start_index = 2

    probe_tasks = [
        asyncio.create_task(_probe_cluster_candidate(idx, uri, semaphore))
        for idx, uri in enumerate(uris[start_index - 1 :], start=start_index)
    ]
    if probe_tasks:
        probe_results.extend(await asyncio.gather(*probe_tasks))
    probe_results.sort(key=lambda row: int(row[0]))

    connected: list[tuple[str, AsyncIOMotorClient]] = []
    failed_candidates: list[tuple[int, str, str]] = []
    last_error: Exception | None = None

    for idx, uri, candidate, candidate_kwargs, error in probe_results:
        if error is None and candidate is not None:
            connected.append((uri, candidate))
            tls_info = "tls=on" if bool(candidate_kwargs.get("tls")) else "tls=auto-or-off"
            logger.info(
                f"MongoDB connected (candidate {idx}, host={_mask_uri_host(uri)}, {tls_info}, "
                f"serverSelectionTimeoutMS={timeout_ms})"
            )
            if not multi_enabled:
                break
            continue

        if error is not None:
            last_error = error
            failed_candidates.append(
                (
                    int(idx),
                    _mask_uri_host(uri),
                    f"{type(error).__name__}: {str(error)[:260]}",
                )
            )

    if not connected:
        for failed_idx, failed_host, failed_detail in failed_candidates:
            logger.warning(
                f"MongoDB connect failed (candidate {failed_idx}: {failed_host}) | {failed_detail}"
            )
        _last_connect_error = last_error
        _last_connect_error_at = time.monotonic()
        raise RuntimeError(
            f"Failed to connect to MongoDB from all configured URIs. Details: {last_error}"
        ) from last_error

    if failed_candidates:
        failed_summary = ", ".join(
            [f"#{failed_idx}:{failed_host}" for failed_idx, failed_host, _ in failed_candidates[:6]]
        )
        logger.info(
            "MongoDB partial connect: "
            f"connected {len(connected)}/{len(uris)} candidate(s); unavailable: {failed_summary}"
        )
        for failed_idx, failed_host, failed_detail in failed_candidates[:3]:
            logger.debug(
                f"MongoDB candidate unavailable (candidate {failed_idx}: {failed_host}) | {failed_detail}"
            )

    if not multi_enabled and len(connected) > 1:
        for _uri, extra_client in connected[1:]:
            try:
                extra_client.close()
            except Exception:
                pass
        connected = connected[:1]

    _cluster_clients = list(connected)
    _client = connected[0][1]
    _cluster_databases = None
    _cluster_databases_key = None
    _database = None
    _database_key = None
    _last_connect_error = None
    _last_connect_error_at = 0.0
    return list(_cluster_clients)


async def _connect_cluster_clients() -> list[tuple[str, AsyncIOMotorClient]]:
    global _connect_clients_inflight
    if _cluster_clients:
        return list(_cluster_clients)

    inflight = _connect_clients_inflight
    if inflight is not None and not inflight.done():
        return list(await inflight)

    async with _connect_clients_lock:
        if _cluster_clients:
            return list(_cluster_clients)
        inflight = _connect_clients_inflight
        if inflight is None or inflight.done():
            inflight = asyncio.create_task(_connect_cluster_clients_impl())
            _connect_clients_inflight = inflight

    try:
        return list(await inflight)
    finally:
        async with _connect_clients_lock:
            if _connect_clients_inflight is inflight and inflight.done():
                _connect_clients_inflight = None


async def _get_cluster_databases() -> list[tuple[str, Any, AsyncIOMotorClient]]:
    global _cluster_databases, _cluster_databases_key
    clients = list(_cluster_clients or [])
    if not clients:
        clients = list(await _connect_cluster_clients())
    current_key = tuple(uri for uri, _client_ref in clients)
    if _cluster_databases and _cluster_databases_key == current_key:
        return list(_cluster_databases)

    database_name = mongo_database_name()
    _storage_settings.name = database_name
    refs: list[tuple[str, Any, AsyncIOMotorClient]] = []
    for uri, client in clients:
        refs.append((uri, client[database_name], client))

    _cluster_databases = refs
    _cluster_databases_key = current_key
    return list(_cluster_databases)


async def get_client() -> AsyncIOMotorClient:
    clients = await _connect_cluster_clients()
    return clients[0][1]


async def get_database():
    global _database, _database_key
    refs = await _get_cluster_databases()
    current_key = tuple(uri for uri, _database_ref, _client_ref in refs)
    if _database is None or _database_key != current_key:
        if _mongo_multi_enabled() and len(refs) > 1:
            _database = _MongoDatabaseProxy(
                mongo_database_name(),
                refs,
                read_mode=_mongo_read_mode(len(refs)),
                write_mode=_mongo_write_mode(len(refs)),
            )
        else:
            _database = refs[0][1]
        _database_key = current_key
    return _database


async def get_collection(name: str):
    database = await get_database()
    return database[str(name or "").strip()]


async def get_connection():
    return await get_database()


async def release_connection(_connection=None):
    return None


async def ping() -> float:
    client = await get_client()
    await client.admin.command("ping")
    return 1.0

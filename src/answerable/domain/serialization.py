from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_dict(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_dict(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.isoformat()
    if isinstance(value, tuple):
        return [to_dict(item) for item in value]
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_dict(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported serialization type: {type(value)!r}")


def from_dict(model: type[T], payload: dict[str, object]) -> T:
    if not is_dataclass(model):
        raise TypeError("from_dict requires a dataclass type")
    hints = get_type_hints(model)
    known = {item.name for item in fields(model) if item.init}
    unknown = set(payload) - {item.name for item in fields(model)}
    if unknown:
        raise ValueError(f"unknown fields for {model.__name__}: {sorted(unknown)}")
    values = {name: _decode(hints[name], payload[name]) for name in known if name in payload}
    return model(**values)


def _decode(annotation: object, value: object) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is datetime:
        if not isinstance(value, str):
            raise TypeError("datetime value must be a string")
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return result
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, dict):
            raise TypeError(f"{annotation.__name__} value must be an object")
        return from_dict(annotation, value)
    if origin is tuple:
        item_type = args[0]
        if not isinstance(value, list):
            raise TypeError("tuple value must be an array")
        return tuple(_decode(item_type, item) for item in value)
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("dict value must be an object")
        return dict(value)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for item_type in args:
            if item_type is not type(None):
                try:
                    return _decode(item_type, value)
                except (TypeError, ValueError):
                    continue
        raise TypeError(f"value does not match {annotation}")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(to_dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

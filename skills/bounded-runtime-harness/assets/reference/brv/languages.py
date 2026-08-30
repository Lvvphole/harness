from __future__ import annotations

import ast
import json


class LanguageError(ValueError):
    pass


SUPPORTED = ("python", "json", "text")


def parse_source(language: str, source: str) -> object:
    """Independent language oracle. Does not trust the decoder.

    A schema-valid candidate object may still contain invalid source.
    JSON-constrained decoding only guarantees the wrapper.
    """
    if language not in SUPPORTED:
        raise LanguageError(f"unsupported language: {language}")
    if language == "python":
        try:
            return ast.parse(source, filename="<candidate>")
        except SyntaxError as exc:
            raise LanguageError(f"python syntax: {exc.msg} (line {exc.lineno})") from exc
    if language == "json":
        try:
            return json.loads(source)
        except json.JSONDecodeError as exc:
            raise LanguageError(f"json syntax: {exc}") from exc
    if not isinstance(source, str):
        raise LanguageError("text source must be a string")
    return source

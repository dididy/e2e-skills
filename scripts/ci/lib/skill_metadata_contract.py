"""Fail-closed parser for the `skills/<name>/agents/openai.yaml` contract.

codex-cli reads this file for every discovered skill, plugin-installed or not
(`codex-rs/ext/skills/src/loader/metadata.rs`), and accepts only `interface`,
`policy`, and `dependencies`. That loader has no `deny_unknown_fields` and warns
then falls back to defaults on a parse error, so an invented key is silently
discarded at runtime instead of reported. This parser is strict precisely
because the runtime is not: the repository shipped four inert files for
months without any surface saying so.

Standard library only, and a deliberately small YAML subset rather than PyYAML.
"""

import re

INTERFACE_KEYS = {
    "display_name",
    "short_description",
    "icon_small",
    "icon_large",
    "brand_color",
    "default_prompt",
}
REQUIRED_INTERFACE_KEYS = ("display_name", "short_description")
POLICY_KEYS = {"allow_implicit_invocation"}
REQUIRED_TOP_KEYS = {"interface"}
ALLOWED_TOP_KEYS = REQUIRED_TOP_KEYS | {"policy", "dependencies"}

# codex-rs/skills/src/interface.rs drops an over-length field rather than
# truncating it, so an unnoticed overrun silently removes the value.
DISPLAY_NAME_MAX_LEN = 64
SHORT_DESCRIPTION_MAX_LEN = 1024
DEFAULT_PROMPT_MAX_LEN = 1024
BRAND_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")


def parse_openai_manifest(path):
    """Return the parsed manifest, raising ValueError on anything unsupported."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("﻿"):
        raise ValueError("UTF-8 BOM is not supported")
    if "\t" in text:
        raise ValueError("tabs are not allowed")
    top = {}
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):
            match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):[ ]+(.+)", line)
            if current is None or not match:
                raise ValueError(
                    f"line {number}: unsupported indentation or nested value"
                )
            key, value = match.groups()
            if re.search(r":\s|(?:^|\s)#", value):
                raise ValueError(f"line {number}: unsupported ambiguous plain scalar")
            block = top[current]
            if key in block:
                raise ValueError(f"line {number}: duplicate {current} key {key!r}")
            block[key] = value
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ ]+(.*))?", line)
        if not match:
            raise ValueError(f"line {number}: unsupported YAML syntax")
        key, value = match.groups()
        if key in top:
            raise ValueError(f"line {number}: duplicate top-level key {key!r}")
        if value is not None and value.strip():
            raise ValueError(f"line {number}: {key} must be a mapping")
        top[key] = {}
        current = key
    if not REQUIRED_TOP_KEYS <= set(top) or not set(top) <= ALLOWED_TOP_KEYS:
        raise ValueError(
            f"top-level keys must include {sorted(REQUIRED_TOP_KEYS)!r} within "
            f"{sorted(ALLOWED_TOP_KEYS)!r}, got {sorted(top)!r}"
        )
    interface = top["interface"]
    unknown = set(interface) - INTERFACE_KEYS
    if unknown:
        raise ValueError(f"unsupported interface keys {sorted(unknown)!r}")
    for required in REQUIRED_INTERFACE_KEYS:
        if not interface.get(required, "").strip():
            raise ValueError(f"interface.{required} must be a non-empty scalar")
    for field, limit in (
        ("display_name", DISPLAY_NAME_MAX_LEN),
        ("short_description", SHORT_DESCRIPTION_MAX_LEN),
        ("default_prompt", DEFAULT_PROMPT_MAX_LEN),
    ):
        value = interface.get(field)
        if value is not None and len(value) > limit:
            raise ValueError(
                f"interface.{field} must be at most {limit} characters, got {len(value)}"
            )
    brand_color = interface.get("brand_color")
    if brand_color is not None and not BRAND_COLOR_PATTERN.fullmatch(brand_color):
        raise ValueError("interface.brand_color must be # followed by 6 hex digits")
    policy = top.get("policy", {})
    unknown_policy = set(policy) - POLICY_KEYS
    if unknown_policy:
        raise ValueError(f"unsupported policy keys {sorted(unknown_policy)!r}")
    if policy.get("allow_implicit_invocation", "true") not in {"true", "false"}:
        raise ValueError("policy.allow_implicit_invocation must be true or false")
    return top


def collect_openai_manifest_errors(path, skill_name):
    """Return every contract error for one skill's manifest, newest checks last."""
    if not path.exists():
        return [f"{path}: missing OpenAI agent manifest"]
    try:
        parsed = parse_openai_manifest(path)
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"{path}: invalid OpenAI agent YAML: {exc}"]
    errors = []
    # The schema carries no `name`, so the directory binding the removed field
    # used to provide now rides on the documented `$<skill>` invocation.
    default_prompt = parsed["interface"].get("default_prompt", "")
    if f"${skill_name}" not in default_prompt:
        errors.append(
            f"{path}: interface.default_prompt must invoke ${skill_name}"
        )
    return errors

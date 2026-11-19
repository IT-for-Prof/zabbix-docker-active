#!/usr/bin/env python3
"""Build "Docker by Zabbix agent 2 active (Custom)" from the official Zabbix template.

The same recipe Zabbix uses for its own `MySQL/PostgreSQL by Zabbix agent 2 active`:
every item key, trigger and macro is kept; items the server polled become active checks;
every UUID is new, so importing the clone never overwrites the official template.

Two language versions share UUIDs and differ only in our own texts (template description,
the added trigger), so importing either one updates an installed clone in place.

    python3 build.py [upstream.yaml]

Copyright (C) Zabbix SIA (official template); changes (C) 2026 Konstantin Tyutyunnik. AGPL-3.0-only.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "upstream" / "template_app_docker.yaml"
OUTPUTS = {"ru": HERE / "template_app_docker_agent2_active.yaml",
           "en": HERE / "template_app_docker_agent2_active_en.yaml"}
BUILD = "1.1.0"

SOURCE_NAME = "Docker by Zabbix agent 2"
# Technical names allow no parentheses; the visible name carries them.
TECH_NAME = "Docker by Zabbix agent 2 active Custom"
VISIBLE_NAME = "Docker by Zabbix agent 2 active (Custom)"
REPO = "https://github.com/IT-for-Prof/zabbix-docker-active"
PASSIVE = {None, "ZABBIX_PASSIVE"}
# Stable seed: rebuilding from the same upstream gives the same UUIDs, so re-import updates in place.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, REPO)

# Zabbix JSONPath sum() fails on an empty array (ZBX-19277): a host without volumes, containers
# or images gets the item unsupported. The agent always sends these arrays (its plugin re-encodes
# /system/df into its own struct), so an empty or null array is the only way these steps fail.
# shortcut: if Docker drops the deprecated /system/df fields, the agent sends empty arrays and
# these items read 0; SIZE_TRIGGER below catches that, the fix then belongs in the agent plugin.
ZERO_ON_EMPTY = {"docker.volumes_size", "docker.containers_size", "docker.images_size"}
SIZE_TRIGGER = {
    "uuid": uuid.UUID(bytes=uuid.uuid5(NAMESPACE, "trigger:size-data").bytes, version=4).hex,
    "expression": f"max(/{TECH_NAME}/docker.layers_size,10m)=0 and min(/{TECH_NAME}/docker.images.total,10m)>0",
    "priority": "WARNING",
    "dependencies": [{"name": "Docker: Service is down", "expression": f"last(/{TECH_NAME}/docker.ping)=0"}],
    "tags": [{"tag": "scope", "value": "availability"}],
}

FOOTER = """
Build:   {build} (official {version})
Author:  Konstantin Tyutyunnik / Константин Тютюнник
Site:    https://itforprof.com
Repo:    {repo}
License: AGPL-3.0-only; official template (c) Zabbix SIA, changes (c) 2026 Konstantin Tyutyunnik
"""
TEXTS = {
    "ru": {
        "description": """\
Docker по активным проверкам. Клон официального шаблона «{source}» (Zabbix {version}): агент сам
отправляет данные серверу или прокси, поэтому входящий порт 10050 не нужен и хост за NAT мониторится.

Отличия от официального:
- 9 объектов, которые сервер опрашивал сам (5 элементов, 2 правила LLD, 2 прототипа), — активные проверки;
  ключи, макросы и LLD те же, поэтому на хост с официальным шаблоном клон не привязывается;
- docker.volumes_size, docker.containers_size и docker.images_size при пустом массиве возвращают 0
  (в официальном шаблоне — ошибка, ZBX-19277);
- добавлен триггер «Docker: данные о размерах не приходят».

Требования: Zabbix 8.0; Zabbix agent 2 с плагином Docker; пользователь агента в группе docker;
в конфиге агента задан ServerActive, а Hostname совпадает с именем хоста в Zabbix.
Прокси, через которую идёт хост, работает на той же основной версии, что сервер. Устаревшая прокси
конфигурацию шаблонов не получает.
Проверка на хосте: zabbix_agent2 -t docker.info
""",
        "trigger_name": "Docker: данные о размерах не приходят",
        "trigger_description": "Образы на хосте есть, а размер слоёв больше 10 минут равен 0: агент не получает "
                               "от Docker размеры. Вероятная причина — Docker убрал устаревшие поля /system/df; "
                               "исправляется обновлением плагина Docker агента. При недоступном агенте данных "
                               "нет, и триггер не срабатывает.",
    },
    "en": {
        "description": """\
Docker on active checks. A clone of the official "{source}" template (Zabbix {version}) in which
the agent sends data to the server or proxy itself, so inbound port 10050 is not needed and hosts
behind NAT can be monitored.

Differences from the official template:
- the 9 objects the server used to poll (5 items, 2 LLD rules, 2 prototypes) are active checks;
  keys, macros and LLD are unchanged, so the clone cannot be linked to a host that has the official
  template;
- docker.volumes_size, docker.containers_size and docker.images_size return 0 on an empty array
  (the official template fails, ZBX-19277);
- an added trigger, "Docker: Size data is not received".

Requirements: Zabbix 8.0; Zabbix agent 2 with the Docker plugin; the agent user in the docker group;
ServerActive set in the agent config and Hostname equal to the host name in Zabbix.
The proxy that serves the host runs the server's major version. An outdated proxy does not receive
template configuration.
Check on the host: zabbix_agent2 -t docker.info
""",
        "trigger_name": "Docker: Size data is not received",
        "trigger_description": "Images exist on the host, but the layer size has been 0 for more than 10 minutes, so the "
                               "agent gets no size data from Docker. The likely cause is that Docker removed the "
                               "deprecated /system/df fields, and the fix is an updated Docker plugin of the agent. "
                               "When the agent is unavailable there is no data, and the trigger does not fire.",
    },
}


def new_uuid(old: str) -> str:
    """Deterministic, but shaped as UUIDv4: Zabbix import rejects other versions."""
    return uuid.UUID(bytes=uuid.uuid5(NAMESPACE, old).bytes, version=4).hex


def _rename(node: Any) -> Any:
    """Point expressions and graph/dashboard references at the clone."""
    if isinstance(node, dict):
        return {k: (new_uuid(v) if k == "uuid" else _rename(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_rename(v) for v in node]
    if isinstance(node, str):
        return TECH_NAME if node == SOURCE_NAME else node.replace(f"/{SOURCE_NAME}/", f"/{TECH_NAME}/")
    return node


def _activate(items: list[dict[str, Any]]) -> None:
    for item in items:
        if item.get("type") in PASSIVE:
            # Keep the upstream field order: type goes right before key.
            rebuilt = {}
            for k, v in item.items():
                if k == "key":
                    rebuilt["type"] = "ZABBIX_ACTIVE"
                if k != "type":
                    rebuilt[k] = v
            item.clear()
            item.update(rebuilt)


def build(upstream: dict[str, Any], lang: str = "ru") -> dict[str, Any]:
    export = dict(upstream["zabbix_export"])
    groups = export["template_groups"]  # the official group, as Zabbix does for its active variants
    (source,) = export["templates"]
    if source["template"] != SOURCE_NAME:
        raise SystemExit(f"unexpected upstream template {source['template']!r}")
    version = source.get("vendor", {}).get("version", "?")
    template = _rename({k: v for k, v in source.items()
                        # readme/wizard describe the passive original; vendor stays as the upstream version.
                        if k not in ("readme", "wizard_ready")})
    template["template"] = TECH_NAME
    template["name"] = VISIBLE_NAME
    text = TEXTS[lang]
    template["description"] = (text["description"] + FOOTER).format(
        source=SOURCE_NAME, version=version, repo=REPO, build=BUILD)
    _activate(template.get("items", []))
    for item in template.get("items", []):
        if item["key"] in ZERO_ON_EMPTY:
            (step,) = item["preprocessing"]
            step.update(error_handler="CUSTOM_VALUE", error_handler_params="0")
    for rule in template.get("discovery_rules", []):
        _activate([rule])
        _activate(rule.get("item_prototypes", []))
    export["templates"] = [template]
    # Multi-item graphs and triggers live beside the template and reference it by name.
    for section in set(export) - {"version", "template_groups", "templates"}:
        export[section] = _rename(export[section])
    trigger = {"uuid": SIZE_TRIGGER["uuid"], "expression": SIZE_TRIGGER["expression"],
               "name": text["trigger_name"], **{k: v for k, v in SIZE_TRIGGER.items() if k not in ("uuid", "expression")},
               "description": text["trigger_description"]}
    export["triggers"] = export.get("triggers", []) + [trigger]
    export["template_groups"] = groups
    return {"zabbix_export": export}


def _walk_items(template: dict[str, Any]):
    yield from template.get("items", [])
    for rule in template.get("discovery_rules", []):
        yield rule
        yield from rule.get("item_prototypes", [])


def check(upstream: dict[str, Any], built: dict[str, Any]) -> None:
    """Invariants the clone must keep; build refuses to write a file that breaks one."""
    src = upstream["zabbix_export"]["templates"][0]
    out = built["zabbix_export"]["templates"][0]
    src_items = {i["key"]: i for i in _walk_items(src)}
    out_items = {i["key"]: i for i in _walk_items(out)}
    assert src_items.keys() == out_items.keys(), "item keys changed"
    for key, item in out_items.items():
        before = src_items[key].get("type")
        after = item.get("type")
        assert after == ("ZABBIX_ACTIVE" if before in PASSIVE else before), f"{key}: {before} -> {after}"
    assert any(i.get("type") == "ZABBIX_ACTIVE" for i in out_items.values()), "nothing activated"

    def uuids(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [v for k, v in node.items() if k == "uuid"] + [u for v in node.values() for u in uuids(v)]
        if isinstance(node, list):
            return [u for v in node for u in uuids(v)]
        return []

    group_uuids = set(uuids(upstream["zabbix_export"]["template_groups"]))
    # Everything outside the template group, top-level graphs/triggers included.
    rest = {k: v for k, v in upstream["zabbix_export"].items() if k != "template_groups"}
    built_rest = {k: v for k, v in built["zabbix_export"].items() if k != "template_groups"}
    old, new = set(uuids(rest)), uuids(built_rest)
    assert len(new) == len(set(new)) == len(old) + 1, "UUIDs lost or duplicated"  # +1: SIZE_TRIGGER
    assert not old & set(new), "an official UUID survived: import would overwrite the original"
    assert not group_uuids & set(new)
    for u in new:
        assert uuid.UUID(u).version == 4 and len(u) == 32, u
    text = yaml.safe_dump(built_rest, allow_unicode=True)
    assert f"/{SOURCE_NAME}/" not in text and f"'{SOURCE_NAME}'" not in text, "reference to the original left"
    assert out["macros"] == src["macros"], "macros changed"
    for key, item in out_items.items():
        expected = src_items[key].get("preprocessing")
        if key in ZERO_ON_EMPTY:
            expected = [dict(expected[0], error_handler="CUSTOM_VALUE", error_handler_params="0")]
        assert item.get("preprocessing") == expected, f"{key}: preprocessing differs from upstream"
    names = {t["name"]: t for i in out["items"] for t in i.get("triggers", [])}
    (size,) = [t for t in built["zabbix_export"]["triggers"] if t["uuid"] == SIZE_TRIGGER["uuid"]]
    for dep in size["dependencies"]:
        assert names.get(dep["name"], {}).get("expression") == dep["expression"], f"dependency {dep['name']!r} not in template"


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # Block style for scripts and descriptions, like Zabbix's own export.
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def render(built: dict[str, Any]) -> str:
    return yaml.dump(built, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=4096)


def main(argv: list[str]) -> int:
    src_path = Path(argv[1]) if len(argv) > 1 else UPSTREAM
    upstream = yaml.safe_load(src_path.read_text(encoding="utf-8"))
    for lang, out_path in OUTPUTS.items():
        built = build(upstream, lang)
        check(upstream, built)
        out_path.write_text(render(built), encoding="utf-8")
        active = sum(1 for i in _walk_items(built["zabbix_export"]["templates"][0]) if i.get("type") == "ZABBIX_ACTIVE")
        print(f"{out_path.name}: {active} active checks, {VISIBLE_NAME} ({lang})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

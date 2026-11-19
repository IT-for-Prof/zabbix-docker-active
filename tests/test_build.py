import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402


@pytest.fixture(scope="module")
def upstream():
    return yaml.safe_load(build.UPSTREAM.read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", sorted(build.OUTPUTS))
def test_committed_template_matches_fresh_build(upstream, lang):
    """The YAML in the repo is exactly what build.py makes from the pinned upstream."""
    assert build.OUTPUTS[lang].read_text(encoding="utf-8") == build.render(build.build(upstream, lang))


def test_language_versions_differ_only_in_our_texts(upstream):
    """Same UUIDs and structure, so importing either version updates an installed clone in place."""
    def strip(built):
        built["zabbix_export"]["templates"][0].pop("description")
        for t in built["zabbix_export"]["triggers"]:
            if t["uuid"] == build.SIZE_TRIGGER["uuid"]:
                t.pop("name"); t.pop("description")
        return built
    ru, en = (build.build(upstream, lang) for lang in ("ru", "en"))
    assert ru["zabbix_export"]["templates"][0]["description"] != en["zabbix_export"]["templates"][0]["description"]
    assert strip(ru) == strip(en)


def test_rendered_yaml_round_trips(upstream):
    built = build.build(upstream)
    assert yaml.safe_load(build.render(built)) == built


def test_check_rejects_a_kept_official_uuid(upstream):
    built = build.build(upstream)
    built["zabbix_export"]["templates"][0]["uuid"] = upstream["zabbix_export"]["templates"][0]["uuid"]
    with pytest.raises(AssertionError, match="UUID"):
        build.check(upstream, built)


def test_check_rejects_a_passive_item_left(upstream):
    built = build.build(upstream)
    item = next(i for i in built["zabbix_export"]["templates"][0]["items"] if i["key"] == "docker.info")
    item["type"] = "ZABBIX_PASSIVE"
    with pytest.raises(AssertionError, match="docker.info"):
        build.check(upstream, built)


def test_rebuild_is_stable(upstream):
    assert build.render(build.build(upstream)) == build.render(build.build(upstream))


def test_top_level_graphs_point_at_the_clone(upstream):
    """Import refused the first build: a top-level graph still named the official template."""
    graphs = build.build(upstream)["zabbix_export"]["graphs"]
    hosts = {i["item"]["host"] for g in graphs for i in g["graph_items"]}
    assert hosts == {build.TECH_NAME}


def test_check_rejects_size_item_without_zero_handler(upstream):
    """ZBX-19277: without the handler a host with no volumes gets docker.volumes_size unsupported."""
    built = build.build(upstream)
    item = next(i for i in built["zabbix_export"]["templates"][0]["items"] if i["key"] == "docker.volumes_size")
    del item["preprocessing"][0]["error_handler"]
    with pytest.raises(AssertionError, match="docker.volumes_size"):
        build.check(upstream, built)


def test_size_trigger_depends_on_a_trigger_of_the_template(upstream):
    built = build.build(upstream)
    (trigger,) = [t for t in built["zabbix_export"]["triggers"] if t["uuid"] == build.SIZE_TRIGGER["uuid"]]
    trigger["dependencies"][0]["expression"] = "last(/x/docker.ping)=0"
    with pytest.raises(AssertionError, match="dependency"):
        build.check(upstream, built)

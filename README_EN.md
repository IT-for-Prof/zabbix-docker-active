# Docker by Zabbix agent 2 active

> Zabbix 8.0 template: the official "Docker by Zabbix agent 2" on active checks, for hosts behind NAT.

The agent sends data to the server or proxy itself, so the host needs no inbound port 10050.
The template is built by `build.py` from Zabbix's official YAML rather than edited by hand, so a new
revision of the official template becomes a new build of the clone with one command.

This file describes the English version, `template_app_docker_agent2_active_en.yaml`. The Russian
version of the same template is `template_app_docker_agent2_active.yaml`, described in
[README.md](README.md). The versions differ only in our own texts: the template description and the
added trigger. They share UUIDs and the template name, so importing either one updates an installed
clone in place and keeps its history.

## Why

The official template has the server or proxy poll the agent. A host behind NAT then needs port 10050
forwarded from outside, which it usually does not have. Zabbix ships active variants for some of its
templates, such as `MySQL by Zabbix agent 2 active` and `PostgreSQL by Zabbix agent 2 active`, but not
for Docker. The clone follows the same recipe: the same keys, triggers and macros, the polled objects
switched to active checks, new UUIDs.

## What differs from the official template

| What | In the clone |
|---|---|
| The 9 objects the server used to poll: `docker.info`, `docker.containers`, `docker.images`, `docker.data_usage`, `docker.ping`, two LLD rules, the prototypes `docker.container_info[…,full]` and `docker.container_stats[…]` | `ZABBIX_ACTIVE`; all other items are dependent and unchanged |
| `docker.volumes_size`, `docker.containers_size`, `docker.images_size` | 0 on an empty array. In the official template the JSONPath aggregate `.sum()` fails on an empty array, so on a host with no volumes, containers or images the item is unsupported (Zabbix issue [ZBX-19277](https://support.zabbix.com/browse/ZBX-19277)) |
| Triggers | the official ones plus one, see "Triggers" |
| UUIDs | new, derived from the official template's UUIDs: importing the clone leaves the official template alone, and a rebuild gives the same UUIDs |
| Name | `Docker by Zabbix agent 2 active (Custom)`, technical name `Docker by Zabbix agent 2 active Custom` |
| Group, vendor | `Templates/Applications` and the official vendor (`Zabbix`, `8.0-2`), which shows the official version the clone is built from. The build version and the author are at the end of the template description |
| readme and wizard | not carried over: they describe the passive template |

Source: `templates/app/docker/template_app_docker.yaml` from the
[Zabbix repository](https://git.zabbix.com/projects/ZBX/repos/zabbix/browse/templates/app/docker),
branch `release/8.0`, commit `22c39f0ccbf4434dbdfe2362a88c4102da25a556`, vendor version 8.0-2.
It is kept unchanged in `upstream/`.

## Triggers

The official triggers are unchanged: "Failed to fetch info data", "Service is down", "Version has
changed" and three container prototypes. One trigger is added:

| Trigger | Severity | Fires when |
|---|---|---|
| Docker: Size data is not received | Warning | images exist on the host (`docker.images.total` above 0) and `docker.layers_size` has been 0 for more than 10 minutes |

The agent's Docker plugin decodes the `/system/df` answer into its own structure and always sends the
volume, container and image arrays. Docker 29 deprecated these fields. If Docker removes them, the
agent sends empty arrays and every size becomes 0. The trigger catches that case; the fix is an
updated agent plugin.

The trigger depends on "Docker: Service is down". When the agent is unavailable there is no data in
the window, so the trigger goes to the unknown state and does not fire. The OS template, such as
"Linux by Zabbix agent active", reports the agent failure.

## Requirements

- Zabbix server 8.0. The proxy that serves the host runs the same major version. An outdated proxy,
  such as 7.0 with an 8.0 server, still collects data but receives no new configuration. On hosts
  behind it the clone does not apply, and items are collected with the old configuration.
- Zabbix agent 2 with the Docker plugin. Checked with agents 7.0 and 8.0.
- The agent user is in the `docker` group, which equals root on the host.
- `ServerActive` is set in the agent config, and `Hostname` equals the host name in Zabbix.

Check on the host: `zabbix_agent2 -t docker.info` returns JSON with `ServerVersion`.

## Installation

1. Import one of the two files (Data collection → Templates → Import). Through the API, review the
   changes with `configuration.importcompare` first.
2. Link the template to the host. The clone cannot be linked to a host that has the official
   template, because they share keys. The next section describes the switch.
3. Check after a minute: `docker.ping` is 1 and its value time is recent.

## Switching from the official template

Keeping history:

1. Unlink the official template without clearing: `host.massremove` with `templateids`. The items
   stay on the host.
2. Link the clone: `host.massadd`. Zabbix matches items, LLD rules and discovered items by key, and
   keeps their itemids and history.
3. Check that the number of `docker.*` items on the host and their itemids are the same as before.
   Discovered items become active on the next LLD run, within 15 minutes.

Without history: unlink the official template with clearing, then link the clone. History and open
problems are lost, and LLD discovers the containers again.

To roll back, do the same in reverse: unlink the clone without clearing and link the official
template.

## Macros

The same as in the official template.

| Macro | Default | Purpose |
|---|---|---|
| `{$DOCKER.LLD.FILTER.CONTAINER.MATCHES}` | `.*` | containers to discover |
| `{$DOCKER.LLD.FILTER.CONTAINER.NOT_MATCHES}` | `CHANGE_IF_NEEDED` | containers to exclude |
| `{$DOCKER.LLD.FILTER.IMAGE.MATCHES}` | `.*` | images to discover |
| `{$DOCKER.LLD.FILTER.IMAGE.NOT_MATCHES}` | `CHANGE_IF_NEEDED` | images to exclude |

## What the template does not catch

- Hosts behind an outdated proxy. The template does not apply there and Zabbix gives no warning;
  `proxy.get` shows such a proxy with `compatibility` 2.
- A slow `/system/df`. If Docker does not answer within the agent timeout, all four size items are
  unsupported. The cause is on the Docker side, and the template does not show it.
- Removal of the `/system/df` fields by Docker during the trigger's 10-minute window: sizes read 0
  until it fires.
- Item and official trigger names stay in English in both versions: translating 195 objects would get
  in the way of rebuilding the clone from a new official revision.

## Build and update

```bash
curl -o upstream/template_app_docker.yaml \
  'https://git.zabbix.com/projects/ZBX/repos/zabbix/raw/templates/app/docker/template_app_docker.yaml?at=refs%2Fheads%2Frelease%2F8.0'
python3 build.py
python3 -m pytest -q
```

`build.py` builds both versions and refuses to write a file when:

- a key is missing or a passive item is left;
- a UUID of the official template survived;
- macros changed;
- an item's preprocessing differs from the official one, except the three size items;
- a dependency of the added trigger is not in the template.

The tests also check that the committed files match a fresh build and that the two versions differ
only in our texts.

Needs Python 3 with PyYAML. For Zabbix 7.x, put the template from the `release/7.x` branch into
`upstream/`. We have not tested such a build.

## License

AGPL-3.0-only, like Zabbix; see [LICENSE](LICENSE). Official template (c) Zabbix SIA. Changes and
build (c) 2026 Konstantin Tyutyunnik, [itforprof.com](https://itforprof.com).

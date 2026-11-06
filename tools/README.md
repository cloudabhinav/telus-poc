# tools/

Generators for the JSON + kustomization files that ArgoCD syncs and `bm-base/push_bm.py`
pushes to MDCAP. Python 3 standard library only; run from anywhere.

| Tool | Creates | Output folder |
|------|---------|---------------|
| `new_bm.py` | a single `BM` | `bms/<name>/` |
| `new_rc.py` | a `ROBINCLUSTER` (RC), NON-HA or HA | `rc/<name>/` |

Each run writes `<name>.json` and a `kustomization.yaml` (referencing `../../bm-base`,
`nameSuffix: -<name>`). Existing folders are not overwritten unless you pass `--force`.
Any `--*-pass` option you omit is prompted for, which keeps it out of shell history.


---

## new_bm.py: one bare-metal node

```bash
tools/new_bm.py <name> --ip <ssh-ip> \
    --ssh-user <user> --ssh-pass <pass> \
    --bmc-user <user> --bmc-pass <pass>
```

### Example
```bash
tools/new_bm.py bm-04 --ip 10.7.82.65 \
    --ssh-user robin --ssh-pass robin123 \
    --bmc-user root  --bmc-pass calvin
```
Creates `bms/bm-04/bm-04.json` and `bms/bm-04/kustomization.yaml`.

### Options
| Option | Default | Notes |
|--------|---------|-------|
| `--ip` | required | SSH host IP; also the BMC IP unless `--bmc-ip` |
| `--bmc-ip` | `--ip` | use when the BMC has its own address |
| `--bm-name` | `<name>` | `metadata.name` sent to MDCAP |
| `--flavor` / `--version` / `--description` | `default` / `1` / empty | metadata |
| `--force` | off | overwrite existing files |

---

## new_rc.py: Robin cluster

Nodes are given with repeated `--node NAME:SSH_IP[:BMC_IP]` (BMC IP defaults to SSH IP).
SSH/BMC credentials are shared by all nodes.

### Mode and roles
- `--install-type auto` (default):
  - 1 node → **NON-HA**
  - `--masters` (default 3) or more nodes → **HA**
  - anything in between → error (pass `--install-type HA|NON-HA` to force)
- First node = `primary_master`.
- HA: the next `masters-1` nodes = `secondary_masters`.
- Every remaining node is appended to `agents[]`.
- HA requires `--vip` and `--vrid`.

### Example 1: single node (NON-HA)
```bash
tools/new_rc.py rc-01 \
    --node qct-35:10.7.90.23:10.7.91.23 \
    --ssh-user root  --ssh-pass robin123 \
    --bmc-user admin --bmc-pass 'Robin123!' \
    --robin-pass Robin123 --location sfo
```
(`--ip 10.7.90.23 --bmc-ip 10.7.91.23` is a shortcut for one node named `rc-01-bm`.)

### Example 2: 3-node HA
```bash
tools/new_rc.py rakuten --vip 10.9.90.203 --vrid 213 \
    --prod true --location sjc --robin-version 5.6.0-128 \
    --node qct-56:10.9.20.239:10.7.91.25 \
    --node qct-57:10.9.20.240:10.7.91.26 \
    --node qct-58:10.9.20.241:10.7.91.27 \
    --ssh-user root  --ssh-pass robin123 \
    --bmc-user admin --bmc-pass 'Lab1234!' \
    --robin-pass Robin123 \
    --config manager.robincp_mode=true --cluster-name baremetal-cluster
```
→ `primary_master: qct-56`, `secondary_masters: [qct-57, qct-58]`, `agents: []`.

### Example 3: HA with an extra agent
Add a 4th `--node qct-59:10.9.20.242:10.7.91.28` to Example 2 →
`agents: ["qct-59"]`.

### Example 4: 5 masters
Add `--masters 5` and five or more `--node` entries.

### Options
| Option | Default | Notes |
|--------|---------|-------|
| `--node` | required (or `--ip`) | repeatable, first = primary master |
| `--install-type` | `auto` | `auto`, `HA`, `NON-HA` |
| `--masters` | `3` | HA master count, and `auto` HA threshold |
| `--vip`, `--vrid` | NON-HA: VIP = first node IP | required for HA |
| `--robin-user` / `--robin-pass` | `admin` / prompt | |
| `--robin-name` | `<name>` | `robin_config.name` |
| `--cluster-name` | none | `robin_config.cluster_name` |
| `--config SECTION.ATTR=VALUE` | none | repeatable, fills `configs[]` |
| `--location` / `--prod` | `sfo` / `false` | labels (`prod` also in HA `robin_config`) |
| `--bmp-name` | none | optional label |
| `--robin-version` | `5.4.3` | |
| `--build-url` | `http://builds.robinsystems.com/master` | |
| `--version` / `--description` | `1.0` / auto | metadata |
| `--hostname` | empty | single-node only |
| `--force` | off | overwrite |

---

## After generating

1. Review the JSON.
2. `git add bms/<name>` (or `rc/<name>`), commit and push.
3. ArgoCD's ApplicationSet creates an app per folder, and the PostSync job runs
   `push_bm.py`, which POSTs the object to MDCAP (or PUTs it if it already exists).

**Note:** [argocd/bm-appset.yaml](../argocd/bm-appset.yaml) currently watches only
`bms/*`. For `rc/*` to deploy, add another entry under `directories:`:
```yaml
      directories:
      - path: bms/*
      - path: rc/*
```

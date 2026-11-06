#!/usr/bin/env python3
"""Generate rcs/<name>/{<name>.json,kustomization.yaml} for a new ROBINCLUSTER (RC).

Nodes are given with repeated --node NAME:SSH_IP[:BMC_IP]  (BMC_IP defaults to SSH_IP).
SSH/BMC credentials are shared by all nodes.

Mode (--install-type auto|HA|NON-HA, default auto):
  auto: 1 node -> NON-HA;  >= --masters (default 3) nodes -> HA;  otherwise an error.
Roles: the first node is primary_master; in HA the next (masters-1) nodes are
secondary_masters; every remaining node is added to agents[].
NON-HA: first node is the master, any extra nodes become agents.

Examples:
  # single node, NON-HA
  tools/new_rc.py rc-01 --node qct-35:10.7.90.23:10.7.91.23 \\
      --ssh-user root --ssh-pass robin123 --bmc-user admin --bmc-pass 'Robin123!' --robin-pass Robin123

  # 3 masters + 1 agent, HA
  tools/new_rc.py rakuten --vip 10.9.90.203 --vrid 213 \\
      --node qct-56:10.9.20.239:10.7.91.25 --node qct-57:10.9.20.240:10.7.91.26 \\
      --node qct-58:10.9.20.241:10.7.91.27 --node qct-59:10.9.20.242:10.7.91.28 \\
      --ssh-user root --ssh-pass robin123 --bmc-user admin --bmc-pass 'Lab1234!' --robin-pass Robin123
Omit any *-pass option to be prompted.
"""
import argparse, getpass, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RC_DIR = "rcs"   # output folder under the repo root

KUSTOMIZATION = """resources:
- ../../bm-base
nameSuffix: -{name}
configMapGenerator:
- name: bm-config
  files:
  - {name}.json
"""

def parse_node(s):
    parts = s.split(":")
    if len(parts) not in (2, 3) or not all(parts):
        sys.exit(f"bad --node '{s}': expected NAME:SSH_IP[:BMC_IP]")
    return {"name": parts[0], "ip": parts[1], "bmc_ip": parts[2] if len(parts) == 3 else parts[1]}

def bm_entry(n, a, creds, full_os=False):
    ssh_pass, bmc_pass = creds
    spec = {"connectors": {
        "bmc": {"bmchost": n["bmc_ip"], "password": bmc_pass, "username": a.bmc_user},
        "ssh": {"sshhost": n["ip"], "password": ssh_pass, "username": a.ssh_user},
    }}
    if full_os:  # single-node layout (as in the original bm-03 template)
        spec = {"config": {
            "os": {"hostname": a.hostname or "", "ip": n["ip"], "mtu": "", "gateway": "",
                   "netmask": "", "domain": "", "dns": "", "search": ""},
            "kickstart_url": "",
            "artifactory": {"os_repo_url": "", "bmaas_artifactory_url": "",
                            "package_repofile_url": "", "robin_build_url": ""}},
            "connectors": spec["connectors"]}
        meta = {"name": n["name"], "version": a.version, "flavor": "default",
                "description": a.description,
                "labels": {"vmaas": "true", "cluster": a.name, "location": a.location}}
    else:
        meta = {"labels": {}, "name": n["name"], "flavor": "", "version": "", "description": ""}
    return {"apiVersion": "mdcap.robin.io/v1", "kind": "BM", "metadata": meta, "spec": spec}

def build(a, nodes, install_type, creds, robin_pass):
    ha = install_type == "HA"
    n_masters = a.masters if ha else 1
    primary = nodes[0]["name"]
    secondary = [n["name"] for n in nodes[1:n_masters]]
    agents = [n["name"] for n in nodes[n_masters:]]
    vip = a.vip or nodes[0]["ip"]

    rc = {
        "build_url": a.build_url,
        "install_type": install_type,
        "name": a.robin_name or a.name,
        "primary_master": primary,
        "robin_password": robin_pass,
        "robin_user": a.robin_user,
        "secondary_masters": secondary,
        "security": {},
        "version": a.robin_version,
        "vip": vip,
        "vrid": a.vrid or "",
        "server_install_args": "--ignore-warnings",
        "agent_install_args": "--ignore-warnings",
        "ip_pools": [],
        "agents": agents,
    }
    if ha:
        rc.update({
            "ha_primary_install_args": "--ignore-warnings",
            "ha_secondary_install_args": "--ignore-warnings",
            "prod": a.prod == "true",
            "host_script_args": "--ignore-warnings --docker-storage-driver=overlay2",
            "k8s_script_args": "--ignore-warnings",
            "k8s_plus_script_args": "--ignore-warnings",
            "robin_script_args": "",
        })
    else:
        rc.update({
            "ui_ip": vip,
            "external_metrics_url": f"https://{vip}:29443/prometheus/graph",
            "internal_metrics_url": f"/robincluster/{a.name}/prometheus/graph",
            "external_guacamole_url": f"https://{vip}:29443/vdi-administrators/vdi/",
            "internal_guacamole_url": f"/robincluster/{a.name}/vmconsole/",
        })
    configs = []
    for c in a.config or []:
        try:
            k, v = c.split("=", 1); section, attr = k.split(".", 1)
        except ValueError:
            sys.exit(f"bad --config '{c}': expected section.attribute=value")
        configs.append({"section": section, "attribute": attr, "value": v})
    if configs or ha:
        rc["configs"] = configs
    if a.cluster_name:
        rc["cluster_name"] = a.cluster_name

    labels = {"location": a.location, "prod": a.prod, "vmaas": "true"}
    if a.bmp_name:
        labels["bmp-name"] = a.bmp_name
    spec = {"robin_config": rc,
            "infra": {n["name"]: bm_entry(n, a, creds, full_os=not ha and len(nodes) == 1)
                      for n in nodes}}
    if not ha:
        spec["connectors"] = {"http": {"ip": nodes[0]["ip"], "port": "29442"}}
    desc = a.description or f"{len(nodes)} node Robin CNP {install_type} Cluster"
    return {"apiVersion": "mdcap.robin.io/v1", "kind": "ROBINCLUSTER",
            "metadata": {"name": a.name, "flavor": "default", "version": a.version,
                         "description": desc, "labels": labels},
            "spec": spec}

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="RC name; also folder name under rcs/")
    p.add_argument("--node", action="append", default=[], metavar="NAME:SSH_IP[:BMC_IP]",
                   help="repeat for each node; first = primary master")
    p.add_argument("--ip", help="single-node shortcut (node named <name>-bm)")
    p.add_argument("--bmc-ip", help="BMC IP for the --ip shortcut")
    p.add_argument("--ssh-user", required=True)
    p.add_argument("--ssh-pass")
    p.add_argument("--bmc-user", required=True)
    p.add_argument("--bmc-pass")
    p.add_argument("--robin-user", default="admin")
    p.add_argument("--robin-pass")
    p.add_argument("--install-type", default="auto", choices=["auto", "HA", "NON-HA"])
    p.add_argument("--masters", type=int, default=3,
                   help="HA: number of master nodes incl. primary (default 3); also the "
                        "node count at which 'auto' switches to HA")
    p.add_argument("--vip", help="cluster VIP (required for HA; default first node IP)")
    p.add_argument("--vrid", help="VRRP id (required for HA)")
    p.add_argument("--robin-name", help="robin_config.name (default: <name>)")
    p.add_argument("--cluster-name", help="robin_config.cluster_name (optional)")
    p.add_argument("--config", action="append", metavar="SECTION.ATTR=VALUE",
                   help="append to robin_config.configs, e.g. manager.robincp_mode=true")
    p.add_argument("--hostname", help="OS hostname (single-node only)")
    p.add_argument("--location", default="sfo")
    p.add_argument("--prod", default="false", choices=["true", "false"])
    p.add_argument("--bmp-name", help="optional bmp-name label")
    p.add_argument("--version", default="1.0")
    p.add_argument("--robin-version", default="5.4.3")
    p.add_argument("--build-url", default="http://builds.robinsystems.com/master")
    p.add_argument("--description", default="")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    a = p.parse_args()

    nodes = [parse_node(s) for s in a.node]
    if a.ip:
        nodes.insert(0, {"name": f"{a.name}-bm", "ip": a.ip, "bmc_ip": a.bmc_ip or a.ip})
    if not nodes:
        sys.exit("specify at least one --node (or --ip)")
    names = [n["name"] for n in nodes]
    if len(set(names)) != len(names):
        sys.exit("duplicate node names")

    it = a.install_type
    if it == "auto":
        if len(nodes) == 1:
            it = "NON-HA"
        elif len(nodes) >= a.masters:
            it = "HA"
        else:
            sys.exit(f"{len(nodes)} nodes is neither single-node nor >= {a.masters} for HA; "
                     "add nodes or pass --install-type explicitly")
    if it == "HA":
        if len(nodes) < a.masters:
            sys.exit(f"HA needs at least {a.masters} nodes (--masters), got {len(nodes)}")
        if not a.vip or not a.vrid:
            sys.exit("HA requires --vip and --vrid")

    ssh_pass = a.ssh_pass or getpass.getpass("SSH password: ")
    bmc_pass = a.bmc_pass or getpass.getpass("BMC password: ")
    robin_pass = a.robin_pass or getpass.getpass("Robin password: ")

    out = os.path.join(ROOT, RC_DIR, a.name)
    jpath = os.path.join(out, f"{a.name}.json")
    kpath = os.path.join(out, "kustomization.yaml")
    if not a.force and (os.path.exists(jpath) or os.path.exists(kpath)):
        sys.exit(f"{out} already has files; use --force to overwrite")
    os.makedirs(out, exist_ok=True)

    with open(jpath, "w") as f:
        json.dump(build(a, nodes, it, (ssh_pass, bmc_pass), robin_pass), f, indent=4)
        f.write("\n")
    with open(kpath, "w") as f:
        f.write(KUSTOMIZATION.format(name=a.name))
    print(f"wrote {jpath} ({it}, {len(nodes)} node(s))\nwrote {kpath}")

if __name__ == "__main__":
    main()

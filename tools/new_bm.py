#!/usr/bin/env python3
"""Generate bms/<name>/{<name>.json,kustomization.yaml} for a new BM.

Example:
  tools/new_bm.py bm-04 --ip 10.7.82.65 \
      --ssh-user robin --ssh-pass robin123 \
      --bmc-user root  --bmc-pass calvin
Omit --ssh-pass/--bmc-pass to be prompted. Use --bmc-ip if the BMC IP differs.
"""
import argparse, getpass, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def build(name, bm_name, ssh_ip, ssh_user, ssh_pass, bmc_ip, bmc_user, bmc_pass,
          flavor, version, description):
    return {
        "apiVersion": "mdcap.robin.io/v1",
        "kind": "BM",
        "metadata": {"labels": {}, "name": bm_name, "flavor": flavor,
                     "version": version, "description": description},
        "spec": {"connectors": {
            "bmc": {"bmchost": bmc_ip, "password": bmc_pass, "username": bmc_user},
            "ssh": {"sshhost": ssh_ip, "password": ssh_pass, "username": ssh_user},
        }},
    }

KUSTOMIZATION = """resources:
- ../../bm-base
nameSuffix: -{name}
configMapGenerator:
- name: bm-config
  files:
  - {name}.json
"""

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="directory name under bms/, e.g. bm-04")
    p.add_argument("--ip", required=True, help="SSH host IP (also BMC IP unless --bmc-ip)")
    p.add_argument("--bmc-ip", help="BMC IP if different from --ip")
    p.add_argument("--ssh-user", required=True)
    p.add_argument("--ssh-pass")
    p.add_argument("--bmc-user", required=True)
    p.add_argument("--bmc-pass")
    p.add_argument("--bm-name", help="metadata.name in MDCAP (default: same as name)")
    p.add_argument("--flavor", default="default")
    p.add_argument("--version", default="1")
    p.add_argument("--description", default="")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    a = p.parse_args()

    ssh_pass = a.ssh_pass or getpass.getpass("SSH password: ")
    bmc_pass = a.bmc_pass or getpass.getpass("BMC password: ")

    out = os.path.join(ROOT, "bms", a.name)
    jpath = os.path.join(out, f"{a.name}.json")
    kpath = os.path.join(out, "kustomization.yaml")
    if not a.force and (os.path.exists(jpath) or os.path.exists(kpath)):
        sys.exit(f"{out} already has files; use --force to overwrite")
    os.makedirs(out, exist_ok=True)

    doc = build(a.name, a.bm_name or a.name, a.ip, a.ssh_user, ssh_pass,
                a.bmc_ip or a.ip, a.bmc_user, bmc_pass,
                a.flavor, a.version, a.description)
    with open(jpath, "w") as f:
        json.dump(doc, f, indent=4); f.write("\n")
    with open(kpath, "w") as f:
        f.write(KUSTOMIZATION.format(name=a.name))
    print(f"wrote {jpath}\nwrote {kpath}")

if __name__ == "__main__":
    main()

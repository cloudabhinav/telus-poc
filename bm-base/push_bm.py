import base64, json, os, ssl, sys, time
import urllib.error, urllib.request

ENGINE = os.environ["MDCAP_ENGINE_URL"].rstrip("/") + "/api/v1"
SECRET_NS = os.environ["MDCAP_SECRET_NAMESPACE"]
SECRET_NAME = os.environ["MDCAP_SECRET_NAME"]
USERNAME = os.environ.get("MDCAP_ADMIN_USERNAME", "admin")
TENANT = os.environ.get("MDCAP_TENANT", "default")
DEFS = os.environ.get("BM_DEFINITIONS", "/config/bms.json")
WAIT_SECS = int(os.environ.get("ENGINE_WAIT_SECS", "600"))
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"

engine_ctx = ssl.create_default_context()
engine_ctx.check_hostname = False
engine_ctx.verify_mode = ssl.CERT_NONE
k8s_ctx = ssl.create_default_context(cafile=f"{SA_DIR}/ca.crt")

def read_admin_password():
    with open(f"{SA_DIR}/token") as fh:
        sa_token = fh.read().strip()
    url = f"https://kubernetes.default.svc/api/v1/namespaces/{SECRET_NS}/secrets/{SECRET_NAME}"
    secret = call("GET", url, headers={"Authorization": f"Bearer {sa_token}"}, ctx=k8s_ctx)
    return base64.b64decode(secret["data"]["MDCAP_ADMIN_PASSWORD"]).decode()

def main():

    creds = read_secret("cno", "mdcap-env-secrets-cno")   # needs your Role/RoleBinding
    print("secret keys:", sorted(creds))                  # never print the valuesi

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", e)
        sys.exit(1)    

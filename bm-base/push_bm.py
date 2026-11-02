import base64, json, glob, os, ssl, sys, time
import urllib.error, urllib.request

ENGINE = os.environ["CONTROLLER_URL"]
SECRET_NS = os.environ["MDCAP_SECRET_NAMESPACE"]
SECRET_NAME = os.environ["MDCAP_SECRET_NAME"]
USERNAME = os.environ.get("MDCAP_ADMIN_USERNAME", "admin")
TENANT = os.environ.get("MDCAP_TENANT", "default")
DEFS = os.environ.get("BM_DEFINITIONS", "/config/bms.json")
WAIT_SECS = int(os.environ.get("ENGINE_WAIT_SECS", "600"))
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
CFG_DIR = os.environ.get("BM_DEFINITIONS_DIR", "/cfg")
engine_ctx = ssl.create_default_context()
engine_ctx.check_hostname = False
engine_ctx.verify_mode = ssl.CERT_NONE
k8s_ctx = ssl.create_default_context(cafile=f"{SA_DIR}/ca.crt")

class ApiError(RuntimeError):
  def __init__(self, msg, code):
      super().__init__(msg)
      self.code = code
def read_admin_password():
    with open(f"{SA_DIR}/token") as fh:
        sa_token = fh.read().strip()
    url = f"https://kubernetes.default.svc/api/v1/namespaces/{SECRET_NS}/secrets/{SECRET_NAME}"
    secret = call("GET", url, headers={"Authorization": f"Bearer {sa_token}"}, ctx=k8s_ctx)
    return base64.b64decode(secret["data"]["MDCAP_ADMIN_PASSWORD"]).decode()

def login(password):
    resp = call("POST", f"{ENGINE}/login",
                {"userid": USERNAME, "password": password, "tenant": TENANT})
    return {"Authorization": resp["token"]}

def call(method, url, body=None, headers=None, ctx=engine_ctx, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        raise ApiError(f"{method} {url} -> {e.code}: {e.read().decode()}", e.code)
    return json.loads(text) if text else {}

def find_uid(name, auth):
      resp = call("GET", f"{ENGINE}/bm?total=True", headers=auth)
      items = resp if isinstance(resp, list) else resp.get("items", [])
      print(json.dumps(resp))
      for item in items:
          if item["metadata"]["name"] == name:
              print(item["metadata"]["uid"])
              return item["metadata"]["uid"]
      raise RuntimeError(f"BM {name} reported as existing but not found in list "
                         f"(response keys: {list(resp) if isinstance(resp, dict) else 'list'})")

def main():
    auth = login(read_admin_password())
    failed = []
    for path in sorted(glob.glob(f"{CFG_DIR}/*.json")):
        with open(path) as fh:
            doc = json.load(fh)
        for bm in (doc if isinstance(doc, list) else [doc]):
            name = bm["metadata"]["name"]
            try:
                try:
                    r = call("POST", f"{ENGINE}/bm", bm, headers=auth)
                    print(f"created BM {name}: {r.get('msg')}", flush=True)
                except ApiError as e:
                    if e.code != 409:
                        raise
                    uid = find_uid(name, auth)
                    call("PUT", f"{ENGINE}/bm/{uid}", bm, headers=auth)
                    print(f"updated BM {name} ({uid})", flush=True)
            except Exception as e:
                print(f"FAILED BM {name}: {e}", flush=True)
                failed.append(name)
    if failed:
      sys.exit(f"failed BMs: {', '.join(failed)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", e)
        sys.exit(1)


from __future__ import annotations
import argparse, json
from pathlib import Path

ALLOWED={"TODO","READY_TO_START","ACTIVE","MATERIALIZING","VERIFYING","PASS","BLOCKED","FROZEN","WAITING_ON_A_TO_D","WAITING_ON_E"}
FINAL={"PASS","FROZEN"}

def validate(state: dict) -> dict:
    assert state["artifact"].startswith("DAO2_MODULE_")
    assert state["module_id"] in {"A","B","C","D","E","F"}
    assert state["status"] in ALLOWED
    gov=state["governance"]
    assert gov["fail_closed"] is True
    assert gov["forward_fill"] is False
    assert gov["silent_proxy_substitution"] is False
    assert gov["model_freeze_allowed"] is False or state["module_id"]=="F"
    assert gov["oos_metrics_allowed"] is False
    if state["status"] in FINAL:
        assert state.get("checkpoint") is not None
        assert state["checkpoint"].get("verified") is True
    return {"valid":True,"module_id":state["module_id"],"status":state["status"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path")
    args=ap.parse_args()
    state=json.loads(Path(args.path).read_text(encoding="utf-8"))
    print(json.dumps(validate(state),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()

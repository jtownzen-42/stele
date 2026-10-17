"""B5 end-to-end licence check against the real Gumroad API.

Run on a computer that can reach api.gumroad.com. The key is read from the environment so it is never
written to a file or shell history by this script:

    PowerShell:  $env:STELE_B5_KEY = "<the test key>" ; python scripts/b5_check.py
    After the sale has been refunded in Gumroad:   python scripts/b5_check.py --after-refund

It uses a throwaway database and an in-memory credential store, so it does not touch your real Stele
settings. Each call to Gumroad is a real check (the first one counts one use on the key).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

import stele.license as lic  # noqa: E402
from stele.db import Database  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def memory_keyring():
    store: dict = {}
    kr = MagicMock()
    kr.set_password.side_effect = lambda s, u, p: store.__setitem__((s, u), p)
    kr.get_password.side_effect = lambda s, u: store.get((s, u))
    kr.delete_password.side_effect = lambda s, u: store.pop((s, u), None)
    return kr


def main() -> int:
    key = os.environ.get("STELE_B5_KEY", "").strip()
    if not key:
        print("Set STELE_B5_KEY first (see the top of this file).")
        return 2
    after_refund = "--after-refund" in sys.argv
    db = Database(Path(tempfile.mkdtemp()) / "b5.db")
    print(f"product_id in use: {lic.product_id()[:6]}... ({'set' if lic.product_id() else 'EMPTY'})")

    with patch("stele.license._keyring", return_value=memory_keyring()):
        if not after_refund:
            ok, msg = lic.activate_license(key, db)
            check("1 valid key activates", ok, msg)
            if not ok:
                print("Stopping: the key did not activate, so the later checks cannot run.")
                return 1
            check("2 Pro features unlock", lic.is_pro(db) and lic.current_tier(db) == "Pro")
            for feature in ("burn", "span"):
                try:
                    lic.require_pro(db, feature)
                    check(f"2b {feature} allowed", True)
                except lic.FeatureLocked as exc:
                    check(f"2b {feature} allowed", False, str(exc))

            with patch("httpx.post", side_effect=httpx.ConnectError("simulated offline")):
                pro, msg = lic.refresh_license(db)
            check("3 offline: Pro stays within the 14-day grace", pro and lic.is_pro(db), msg)

            pro, msg = lic.refresh_license(db)  # real network again
            check("4 online re-check keeps Pro", pro, msg)

            bad_ok, bad_msg = lic.activate_license("0000AAAA-0000BBBB-0000CCCC-0000DDDD", Database(Path(tempfile.mkdtemp()) / "x.db"))
            check("5 a made-up key is rejected", not bad_ok, bad_msg)
            print("\nNext: have the test sale refunded in Gumroad, then run:  python scripts/b5_check.py --after-refund")
        else:
            ok, msg = lic.activate_license(key, db)
            revoked = any(w in msg.lower() for w in ("refund", "disabled", "turned off", "charged back"))
            check("6 revoked (refunded or disabled) key is rejected", not ok and revoked, msg)
            check("7 Pro stays locked", not lic.is_pro(db))

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

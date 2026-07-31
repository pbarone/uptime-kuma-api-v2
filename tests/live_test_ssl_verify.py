"""
Live verification for Bug B (#65) -- ``ssl_verify`` must reach the HTTP leg.

Not a pytest test. The filename deliberately starts with ``live_test_`` rather
than ``test_``: pytest's default discovery collects ``test_*.py`` and
``*_test.py``, so this prefix keeps the script out of every pytest run,
including a bare ``pytest tests/``. Do not rename it.

What is under test:
    ``UptimeKumaApi.__init__`` now stores ``self.ssl_verify``, and
    ``get_status_page`` passes ``verify=self.ssl_verify`` to ``requests.get``.
    Before the fix no ``verify=`` argument was passed at all, so the HTTP leg
    always verified the certificate even when the caller asked for
    ``ssl_verify=False``. The socket.io leg honoured the flag both before and
    after, which is why a connection succeeding proves nothing on its own.

Why the discriminator check matters:
    Reading a status page successfully with ``ssl_verify=False`` only means
    something if the same read FAILS with ``ssl_verify=True``. Otherwise the
    endpoint might simply be presenting a trusted certificate and nothing was
    ever being verified. Both directions are checked here.

Scope: this script reads a status page. It creates one only if the instance has
none, and deletes that one again on the way out. It does not touch monitors,
notifications or settings.

Expected noise: ``urllib3`` prints ``InsecureRequestWarning`` for every request
made with ``verify=False``. That is expected and is not a failure.

Output is ASCII only. The Windows console defaults to cp1252 and raises
UnicodeEncodeError on check marks, box-drawing characters and arrows, which has
crashed a script mid-run before. Use PASS / FAIL / SKIP / ->.

Configuration:
    Add to tests/.env:
        UPTIME_KUMA_SELFSIGNED_URL=https://kuma-ss.pbarone.com/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

    UPTIME_KUMA_SELFSIGNED_URL must front the DISPOSABLE instance through Nginx
    Proxy Manager using the custom self-signed certificate whose SAN is
    kuma-ss.pbarone.com. The certificate has to be untrusted for this script to
    prove anything; see the guard in step 1.

Usage:
    .venv/Scripts/python tests/live_test_ssl_verify.py

Exit code is 0 only if every check passed.
"""
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import requests

from uptime_kuma_api import UptimeKumaApi, UptimeKumaException

PREFIX = "[TEST] "
TEST_SLUG = "test-ssl-verify"

results = []


def record(label: str, ok: bool, detail: str = "") -> bool:
    """Record one check result and report it as it happens."""
    results.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if detail:
        print(f"          {detail}")
    return ok


def guard_endpoint_is_untrusted(url: str) -> None:
    """Refuse to run unless the endpoint's certificate is actually untrusted.

    The whole script is a comparison between ssl_verify=False (must work) and
    ssl_verify=True (must fail). If the endpoint presents a publicly trusted
    certificate then both succeed, every check passes, and the result is
    meaningless. So a successful default-verification connect is a hard abort,
    not a pass.
    """
    print("Step 1: endpoint must be untrusted (ssl_verify defaults to True)")
    api = None
    try:
        # __init__ calls connect(), which fails TLS verification here.
        api = UptimeKumaApi(url)
    except UptimeKumaException as e:
        record(
            "ssl_verify=True is rejected by the self-signed endpoint",
            True,
            f"raised UptimeKumaException as expected -> {e}",
        )
        return
    except Exception as e:
        # Some other failure (DNS, refused, proxy down) is not the untrusted-TLS
        # signal we need, so it cannot be accepted as the guard passing.
        if api is not None:
            api.disconnect()
        raise SystemExit(
            "ABORT: connecting with ssl_verify=True failed, but not with the\n"
            f"       expected UptimeKumaException: {type(e).__name__}: {e}\n"
            f"       Check that {url} is reachable at all."
        )

    # Reached only when verification SUCCEEDED, which breaks the premise.
    api.disconnect()
    raise SystemExit(
        "ABORT: connecting to\n"
        f"         {url}\n"
        "       with ssl_verify=True SUCCEEDED. The endpoint is presenting a\n"
        "       PUBLICLY TRUSTED certificate, so this script cannot prove\n"
        "       anything: with a trusted cert, verify=True and verify=False\n"
        "       behave identically and every check below would pass whether or\n"
        "       not the fix is present.\n"
        "\n"
        "       Most likely cause: the Nginx Proxy Manager host for this\n"
        "       hostname is serving the *.pbarone.com Let's Encrypt wildcard\n"
        "       instead of the custom self-signed certificate.\n"
        "\n"
        "       Fix: open that proxy host in Nginx Proxy Manager, go to the SSL\n"
        "       tab, and select the custom self-signed certificate whose SAN is\n"
        "       kuma-ss.pbarone.com. Then re-run this script."
    )


def main() -> int:
    try:
        url = os.environ["UPTIME_KUMA_SELFSIGNED_URL"]
        username = os.environ["UPTIME_KUMA_USERNAME"]
        password = os.environ["UPTIME_KUMA_PASSWORD"]
    except KeyError as e:
        raise SystemExit(
            f"ABORT: {e.args[0]} is not set. Add UPTIME_KUMA_SELFSIGNED_URL, "
            "UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD to tests/.env."
        )

    print(f"Target: {url}")
    print("Note: urllib3 InsecureRequestWarning output below is expected.")
    print()

    guard_endpoint_is_untrusted(url)
    print()

    print("Step 2: socket.io leg honours ssl_verify=False")
    try:
        api = UptimeKumaApi(url, ssl_verify=False)
    except Exception as e:
        record(
            "connect with ssl_verify=False",
            False,
            f"{type(e).__name__}: {e}",
        )
        print()
        print("Cannot continue without a connection.")
        return 1
    record("connect with ssl_verify=False", True)

    created_slug = None
    try:
        print()
        print("Step 3: login")
        api.login(username, password)
        record("login", True, f"server version {api.version}")

        print()
        print("Step 4: obtain a status page slug to read")
        pages = api.get_status_pages()
        existing = [p.get("slug") for p in pages if p.get("slug")]
        if existing:
            slug = existing[0]
            record(
                "status page available",
                True,
                f"reusing existing slug={slug!r} (no page created)",
            )
        else:
            api.add_status_page(TEST_SLUG, f"{PREFIX}SSL Verify")
            created_slug = TEST_SLUG
            slug = TEST_SLUG
            record(
                "status page available",
                True,
                f"created slug={slug!r} (will be deleted during cleanup)",
            )

        print()
        print("Step 5: the fix -- get_status_page works with ssl_verify=False")
        try:
            page = api.get_status_page(slug)
        except Exception as e:
            # Pre-fix this is requests.exceptions.SSLError, because no verify=
            # argument reached requests.get.
            record(
                "get_status_page with ssl_verify=False",
                False,
                f"{type(e).__name__}: {e}",
            )
        else:
            ok = isinstance(page, dict) and "slug" in page
            record(
                "get_status_page with ssl_verify=False",
                ok,
                "" if ok else f"expected a dict containing 'slug', got {type(page).__name__}: {page!r}",
            )
            # The dual-key contract: 2.1.0 renamed incident -> incidents, and
            # the library returns both regardless of server version.
            missing = [k for k in ("incident", "incidents") if k not in page]
            record(
                "response carries both 'incident' and 'incidents'",
                not missing,
                "" if not missing else f"ABSENT: {', '.join(missing)}",
            )

        print()
        print("Step 6: discriminator -- the same read must FAIL with ssl_verify=True")
        # The attribute is flipped on the live instance rather than building a
        # second UptimeKumaApi(url, ssl_verify=True): that constructor calls
        # connect(), which fails TLS verification and raises before
        # get_status_page is ever reachable (that is exactly what step 1
        # asserts). Flipping the attribute is the only way to isolate the HTTP
        # leg while leaving the already-established socket.io leg intact.
        try:
            api.ssl_verify = True
            try:
                page = api.get_status_page(slug)
            except requests.exceptions.SSLError as e:
                record(
                    "get_status_page with ssl_verify=True raises SSLError",
                    True,
                    f"raised SSLError as expected -> {type(e).__name__}",
                )
            except Exception as e:
                record(
                    "get_status_page with ssl_verify=True raises SSLError",
                    False,
                    f"expected requests.exceptions.SSLError, got {type(e).__name__}: {e}",
                )
            else:
                record(
                    "get_status_page with ssl_verify=True raises SSLError",
                    False,
                    "the call SUCCEEDED, so nothing is being verified on the HTTP "
                    f"leg; step 5 proves nothing. Returned keys: {sorted(page)[:5]}",
                )
        finally:
            api.ssl_verify = False

    finally:
        print()
        print("Cleanup")
        if created_slug:
            try:
                api.delete_status_page(created_slug)
                print(f"  deleted status page created by this script: {created_slug!r}")
            except Exception as e:
                print(f"  FAILED to delete {created_slug!r}: {type(e).__name__}: {e}")
                print("  Remove it manually in the UI.")
        else:
            print("  nothing to delete (no status page was created)")
        api.disconnect()
        print("  disconnected")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed

    print()
    print("=" * 60)
    print(f"  {passed} passed, {failed} failed, {len(results)} checks total")
    print("=" * 60)

    if failed:
        print()
        print("Failed checks:")
        for label, ok, detail in results:
            if not ok:
                print(f"  {label}")
                if detail:
                    print(f"    {detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

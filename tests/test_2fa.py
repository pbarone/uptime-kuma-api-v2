import unittest
from urllib import parse

from uptime_kuma_test_case import UptimeKumaTestCase


def parse_secret(uri):
    query = parse.urlsplit(uri).query
    params = dict(parse.parse_qsl(query))
    return params["secret"]


def generate_token(secret):
    # Imported here rather than at module scope. pytest applies the
    # `integration` marker AFTER collection, and collection imports every test
    # module -- so a module-scope `import pyotp` aborts collection of the whole
    # session when pyotp is absent, taking the unit suite down over a dependency
    # of a test that run deselects anyway. That is what happened when the marker
    # landed: CI has no pyotp (it is declared in dev-requirements.txt, which the
    # test jobs do not install), and all six matrix jobs died at
    # `ERROR collecting tests/test_2fa.py` having run nothing.
    #
    # A lazy import rather than pytest.importorskip, because run_tests.sh drives
    # these tests through `unittest discover` and this module should not need
    # pytest importable to run. Nothing is silently skipped either: whoever
    # actually runs this test still gets a plain ModuleNotFoundError if pyotp is
    # missing, which is the right outcome for a dependency they asked to use.
    import pyotp

    totp = pyotp.TOTP(secret)
    return totp.now()


class Test2FA(UptimeKumaTestCase):
    def test_2fa(self):
        # check 2fa is disabled
        r = self.api.twofa_status()
        self.assertEqual(r["status"], False)

        # prepare 2fa
        r = self.api.prepare_2fa(self.password)
        uri = r["uri"]
        self.assertTrue(uri.startswith("otpauth://totp/"))
        secret = parse_secret(uri)

        # verify token
        token = generate_token(secret)
        r = self.api.verify_token(token, self.password)
        self.assertEqual(r["valid"], True)

        # save 2fa
        r = self.api.save_2fa(self.password)
        self.assertEqual(r["msg"], "2FA Enabled.")

        # check 2fa is enabled
        r = self.api.twofa_status()
        self.assertEqual(r["status"], True)

        # relogin using the totp token
        self.api.logout()
        token = generate_token(secret)
        self.api.login(self.username, self.password, token)

        # disable 2fa
        r = self.api.disable_2fa(self.password)
        self.assertEqual(r["msg"], "2FA Disabled.")


if __name__ == '__main__':
    unittest.main()

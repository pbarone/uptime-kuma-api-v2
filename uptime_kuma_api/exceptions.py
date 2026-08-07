class UptimeKumaException(Exception):
    """
    There was an exception that occurred while communicating with Uptime Kuma.
    """


class Timeout(UptimeKumaException):
    """
    A timeout has occurred while communicating with Uptime Kuma.
    """


class UnsupportedFieldWarning(UserWarning):
    """
    A monitor field was left out of the payload because the connected Uptime Kuma
    server does not implement it.

    Emitted once per :meth:`~uptime_kuma_api.UptimeKumaApi.add_monitor` or
    :meth:`~uptime_kuma_api.UptimeKumaApi.edit_monitor` call that withholds at
    least one field, naming every withheld field, the server version each one
    requires, and the version the server actually reports. See
    :ref:`v2-only-fields` for the rule.

    **This is a warning, not an exception, so ``except UptimeKumaException`` does
    not catch it.** It is defined here because it belongs with the other things
    the library raises at the caller -- and under the escalation below it is
    genuinely raised.

    Callers who would rather a request for an unsupported field fail loudly than
    be dropped with a warning can escalate it::

        import warnings
        from uptime_kuma_api import UnsupportedFieldWarning

        warnings.simplefilter("error", UnsupportedFieldWarning)

    The call then raises instead of sending a payload, which makes the strict
    behaviour available without the library imposing it on anyone. It can equally
    be silenced::

        warnings.simplefilter("ignore", UnsupportedFieldWarning)
    """

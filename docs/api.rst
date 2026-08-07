.. _api:


Main Interface
--------------

.. module:: uptime_kuma_api

.. autoclass:: UptimeKumaApi
    :inherited-members:


.. _v2-only-fields:

Version-gated monitor fields
----------------------------

This library supports a range of Uptime Kuma server versions from one codebase,
and some monitor fields only exist from a certain server version onward. When you
supply a field the connected server does not implement, there is one rule:

    **The field is left out of the payload, and you are told once per call.**

    The exception is a field that would change the monitor's up/down *verdict*
    rather than *how* the check runs. Such a field raises instead, because
    dropping it would hand back a monitor that reports success against criteria
    you never set. ``conditions`` is currently the only field in that category.

That is the whole rule, and it applies to every version-gated monitor field on
:meth:`~uptime_kuma_api.UptimeKumaApi.add_monitor` and
:meth:`~uptime_kuma_api.UptimeKumaApi.edit_monitor` -- including any added in
future, so the behaviour of a new field is inherited rather than decided again.

**How you are told.** A single :class:`UnsupportedFieldWarning` is emitted per
call, naming every field that was withheld, the server version each one requires,
and the version your server reports. One warning per call, not one per field.

**Which fields, and from which version.** The set is internal, because it tracks
what the server supports rather than anything you configure. You do not need to
consult it: supply the fields you want and the warning names any your server
cannot take. Every entry has been checked against a real 1.23.2 server rather
than assumed.

**If you would rather it failed loudly.** Escalate the category, and a request for
an unsupported field raises instead of being dropped, before anything is sent::

    import warnings
    from uptime_kuma_api import UnsupportedFieldWarning

    warnings.simplefilter("error", UnsupportedFieldWarning)

Or silence it, if you deploy against mixed server versions deliberately and the
warning is noise::

    warnings.simplefilter("ignore", UnsupportedFieldWarning)

**What this is not.** Argument validation is unaffected and version-independent:
an out-of-range or wrongly-typed value still raises ``ValueError`` or
``TypeError`` on every server version, because a bad value is a bad value
regardless of what the server would have accepted.

Monitor *types* are governed separately. A type the server has no implementation
of raises rather than being degraded, since a type is the thing being requested
rather than a parameter whose loss can be absorbed.


MonitorBuilder
--------------

.. autoclass:: MonitorBuilder
    :members:


Enums
-----

.. autoclass:: AuthMethod
    :members:

.. autoclass:: MonitorType
    :members:

.. autoclass:: MonitorStatus
    :members:

.. autoclass:: NotificationType
    :members:

.. autoclass:: ProxyProtocol
    :members:

.. autoclass:: IncidentStyle
    :members:

.. autoclass:: DockerType
    :members:

.. autoclass:: MaintenanceStrategy
    :members:

.. autoclass:: Event
    :members:
    :undoc-members:


Notification provider metadata
------------------------------

Two module-level tables describe the arguments each notification provider
accepts. They are generated from Uptime Kuma's own frontend, so their contents
track the providers the server supports.

Between them they drive every argument check on the notification methods:
rejecting unknown keyword arguments, enforcing the required ones for the chosen
provider, range-checking the numeric ones, and clearing a previous provider's
options when :meth:`~uptime_kuma_api.UptimeKumaApi.edit_notification` changes a
notification's type. They are exported so that callers can inspect the same
tables the library validates against.

.. py:data:: notification_provider_options

    Keyed by :class:`NotificationType`, with one entry per member. Each value
    maps an option's keyword-argument name to a description of it::

        notification_provider_options[NotificationType.ALERTA]
        # {'alertaApiEndpoint': {'type': 'str', 'required': True},
        #  'alertaApiKey': {'type': 'str', 'required': True},
        #  ... }

    ``type`` is a Python type name as a string (``'str'``, ``'int'``, ``'bool'``,
    ``'list'``, ``'dict'``) and ``required`` marks the options that must be
    supplied for that provider. There is an entry for every member of
    :class:`NotificationType`, so the table is too large to reproduce here; read
    it from the attribute directly.

.. py:data:: notification_provider_conditions

    Numeric bounds for the few options that have them, keyed by the option name
    rather than by provider, since an option name is unique across providers.
    Each value carries ``min`` and ``max``, and a value outside that range is
    rejected before any request is sent::

        {'gotifyPriority': {'min': 0, 'max': 10},
         'ntfyPriority': {'min': 1, 'max': 5},
         ... }


Exceptions and warnings
-----------------------

.. autoexception:: UptimeKumaException

.. autoexception:: Timeout

.. autoexception:: UnsupportedFieldWarning

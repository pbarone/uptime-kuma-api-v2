.. _api:


Main Interface
--------------

.. module:: uptime_kuma_api

.. autoclass:: UptimeKumaApi
    :inherited-members:


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


Exceptions
----------

.. autoexception:: UptimeKumaException

.. autoexception:: Timeout

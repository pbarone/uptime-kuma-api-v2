from enum import Enum


class Event(str, Enum):
    """
    Enumerate the socket.io event names the server emits.

    Each member's value is the event name as it appears on the wire. The library
    subscribes to these internally to maintain its cached view of monitors,
    notifications, proxies, status pages and the rest; they are exported so that
    callers can refer to an event by name rather than by string literal.
    """

    CONNECT = "connect"
    DISCONNECT = "disconnect"
    MONITOR_LIST = "monitorList"
    UPDATE_MONITOR_INTO_LIST = "updateMonitorIntoList"
    DELETE_MONITOR_FROM_LIST = "deleteMonitorFromList"
    NOTIFICATION_LIST = "notificationList"
    PROXY_LIST = "proxyList"
    STATUS_PAGE_LIST = "statusPageList"
    HEARTBEAT_LIST = "heartbeatList"
    IMPORTANT_HEARTBEAT_LIST = "importantHeartbeatList"
    AVG_PING = "avgPing"
    UPTIME = "uptime"
    HEARTBEAT = "heartbeat"
    INFO = "info"
    CERT_INFO = "certInfo"
    DOCKER_HOST_LIST = "dockerHostList"
    AUTO_LOGIN = "autoLogin"
    INIT_SERVER_TIMEZONE = "initServerTimezone"
    MAINTENANCE_LIST = "maintenanceList"
    API_KEY_LIST = "apiKeyList"

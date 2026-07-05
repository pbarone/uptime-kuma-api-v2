from .monitor_type import MonitorType


class MonitorBuilder:
    """Fluent builder for constructing monitor configuration dictionaries.

    Usage::

        builder = MonitorBuilder()
        config = (
            builder
            .type(MonitorType.HTTP)
            .name("My Monitor")
            .url("https://example.com")
            .interval(60)
            .build()
        )
        api.add_monitor(**config)

    Credit: Cherry-picked from PR #86 by @markus-seidl.
    """

    def __init__(self):
        self._data = {}

    # ── Common parameters ────────────────────────────────────────────────

    def type(self, value: MonitorType) -> "MonitorBuilder":
        self._data["type"] = value
        return self

    def name(self, value: str) -> "MonitorBuilder":
        self._data["name"] = value
        return self

    def parent(self, value: int) -> "MonitorBuilder":
        self._data["parent"] = value
        return self

    def description(self, value: str) -> "MonitorBuilder":
        self._data["description"] = value
        return self

    def interval(self, value: int) -> "MonitorBuilder":
        self._data["interval"] = value
        return self

    def retryInterval(self, value: int) -> "MonitorBuilder":
        self._data["retryInterval"] = value
        return self

    def resendInterval(self, value: int) -> "MonitorBuilder":
        self._data["resendInterval"] = value
        return self

    def maxretries(self, value: int) -> "MonitorBuilder":
        self._data["maxretries"] = value
        return self

    def upsideDown(self, value: bool) -> "MonitorBuilder":
        self._data["upsideDown"] = value
        return self

    def notificationIDList(self, value: list) -> "MonitorBuilder":
        self._data["notificationIDList"] = value
        return self

    def httpBodyEncoding(self, value: str) -> "MonitorBuilder":
        self._data["httpBodyEncoding"] = value
        return self

    def conditions(self, value: list) -> "MonitorBuilder":
        self._data["conditions"] = value
        return self

    # ── HTTP / KEYWORD / JSON_QUERY / REAL_BROWSER ───────────────────────

    def url(self, value: str) -> "MonitorBuilder":
        self._data["url"] = value
        return self

    def maxredirects(self, value: int) -> "MonitorBuilder":
        self._data["maxredirects"] = value
        return self

    def accepted_statuscodes(self, value: list) -> "MonitorBuilder":
        self._data["accepted_statuscodes"] = value
        return self

    def expiryNotification(self, value: bool) -> "MonitorBuilder":
        self._data["expiryNotification"] = value
        return self

    def ignoreTls(self, value: bool) -> "MonitorBuilder":
        self._data["ignoreTls"] = value
        return self

    def proxyId(self, value: int) -> "MonitorBuilder":
        self._data["proxyId"] = value
        return self

    def method(self, value: str) -> "MonitorBuilder":
        self._data["method"] = value
        return self

    def body(self, value: str) -> "MonitorBuilder":
        self._data["body"] = value
        return self

    def headers(self, value: str) -> "MonitorBuilder":
        self._data["headers"] = value
        return self

    def authMethod(self, value) -> "MonitorBuilder":
        self._data["authMethod"] = value
        return self

    def tlsCert(self, value: str) -> "MonitorBuilder":
        self._data["tlsCert"] = value
        return self

    def tlsKey(self, value: str) -> "MonitorBuilder":
        self._data["tlsKey"] = value
        return self

    def tlsCa(self, value: str) -> "MonitorBuilder":
        self._data["tlsCa"] = value
        return self

    def basic_auth_user(self, value: str) -> "MonitorBuilder":
        self._data["basic_auth_user"] = value
        return self

    def basic_auth_pass(self, value: str) -> "MonitorBuilder":
        self._data["basic_auth_pass"] = value
        return self

    def authDomain(self, value: str) -> "MonitorBuilder":
        self._data["authDomain"] = value
        return self

    def authWorkstation(self, value: str) -> "MonitorBuilder":
        self._data["authWorkstation"] = value
        return self

    def oauth_auth_method(self, value: str) -> "MonitorBuilder":
        self._data["oauth_auth_method"] = value
        return self

    def oauth_token_url(self, value: str) -> "MonitorBuilder":
        self._data["oauth_token_url"] = value
        return self

    def oauth_client_id(self, value: str) -> "MonitorBuilder":
        self._data["oauth_client_id"] = value
        return self

    def oauth_client_secret(self, value: str) -> "MonitorBuilder":
        self._data["oauth_client_secret"] = value
        return self

    def oauth_scopes(self, value: str) -> "MonitorBuilder":
        self._data["oauth_scopes"] = value
        return self

    def timeout(self, value: int) -> "MonitorBuilder":
        self._data["timeout"] = value
        return self

    # ── KEYWORD ──────────────────────────────────────────────────────────

    def keyword(self, value: str) -> "MonitorBuilder":
        self._data["keyword"] = value
        return self

    def invertKeyword(self, value: bool) -> "MonitorBuilder":
        self._data["invertKeyword"] = value
        return self

    # ── GRPC_KEYWORD ─────────────────────────────────────────────────────

    def grpcUrl(self, value: str) -> "MonitorBuilder":
        self._data["grpcUrl"] = value
        return self

    def grpcEnableTls(self, value: bool) -> "MonitorBuilder":
        self._data["grpcEnableTls"] = value
        return self

    def grpcServiceName(self, value: str) -> "MonitorBuilder":
        self._data["grpcServiceName"] = value
        return self

    def grpcMethod(self, value: str) -> "MonitorBuilder":
        self._data["grpcMethod"] = value
        return self

    def grpcProtobuf(self, value: str) -> "MonitorBuilder":
        self._data["grpcProtobuf"] = value
        return self

    def grpcBody(self, value: str) -> "MonitorBuilder":
        self._data["grpcBody"] = value
        return self

    def grpcMetadata(self, value: str) -> "MonitorBuilder":
        self._data["grpcMetadata"] = value
        return self

    # ── Hostname / port ──────────────────────────────────────────────────

    def hostname(self, value: str) -> "MonitorBuilder":
        self._data["hostname"] = value
        return self

    def packetSize(self, value: int) -> "MonitorBuilder":
        self._data["packetSize"] = value
        return self

    def port(self, value: int) -> "MonitorBuilder":
        self._data["port"] = value
        return self

    # ── DNS ──────────────────────────────────────────────────────────────

    def dns_resolve_server(self, value: str) -> "MonitorBuilder":
        self._data["dns_resolve_server"] = value
        return self

    def dns_resolve_type(self, value: str) -> "MonitorBuilder":
        self._data["dns_resolve_type"] = value
        return self

    # ── MQTT ─────────────────────────────────────────────────────────────

    def mqttUsername(self, value: str) -> "MonitorBuilder":
        self._data["mqttUsername"] = value
        return self

    def mqttPassword(self, value: str) -> "MonitorBuilder":
        self._data["mqttPassword"] = value
        return self

    def mqttTopic(self, value: str) -> "MonitorBuilder":
        self._data["mqttTopic"] = value
        return self

    def mqttSuccessMessage(self, value: str) -> "MonitorBuilder":
        self._data["mqttSuccessMessage"] = value
        return self

    def mqttWebsocketPath(self, value: str) -> "MonitorBuilder":
        self._data["mqttWebsocketPath"] = value
        return self

    def mqttCheckType(self, value: str) -> "MonitorBuilder":
        self._data["mqttCheckType"] = value
        return self

    # ── Database ─────────────────────────────────────────────────────────

    def databaseConnectionString(self, value: str) -> "MonitorBuilder":
        self._data["databaseConnectionString"] = value
        return self

    def databaseQuery(self, value: str) -> "MonitorBuilder":
        self._data["databaseQuery"] = value
        return self

    # ── Docker ───────────────────────────────────────────────────────────

    def docker_container(self, value: str) -> "MonitorBuilder":
        self._data["docker_container"] = value
        return self

    def docker_host(self, value: int) -> "MonitorBuilder":
        self._data["docker_host"] = value
        return self

    # ── Radius ───────────────────────────────────────────────────────────

    def radiusUsername(self, value: str) -> "MonitorBuilder":
        self._data["radiusUsername"] = value
        return self

    def radiusPassword(self, value: str) -> "MonitorBuilder":
        self._data["radiusPassword"] = value
        return self

    def radiusSecret(self, value: str) -> "MonitorBuilder":
        self._data["radiusSecret"] = value
        return self

    def radiusCalledStationId(self, value: str) -> "MonitorBuilder":
        self._data["radiusCalledStationId"] = value
        return self

    def radiusCallingStationId(self, value: str) -> "MonitorBuilder":
        self._data["radiusCallingStationId"] = value
        return self

    # ── Gamedig ──────────────────────────────────────────────────────────

    def game(self, value: str) -> "MonitorBuilder":
        self._data["game"] = value
        return self

    def gamedigGivenPortOnly(self, value: bool) -> "MonitorBuilder":
        self._data["gamedigGivenPortOnly"] = value
        return self

    def gamedigToken(self, value: str) -> "MonitorBuilder":
        self._data["gamedigToken"] = value
        return self

    # ── JSON_QUERY ───────────────────────────────────────────────────────

    def jsonPath(self, value: str) -> "MonitorBuilder":
        self._data["jsonPath"] = value
        return self

    def expectedValue(self, value: str) -> "MonitorBuilder":
        self._data["expectedValue"] = value
        return self

    def jsonPathOperator(self, value: str) -> "MonitorBuilder":
        self._data["jsonPathOperator"] = value
        return self

    # ── Kafka ────────────────────────────────────────────────────────────

    def kafkaProducerBrokers(self, value: list) -> "MonitorBuilder":
        self._data["kafkaProducerBrokers"] = value
        return self

    def kafkaProducerTopic(self, value: str) -> "MonitorBuilder":
        self._data["kafkaProducerTopic"] = value
        return self

    def kafkaProducerMessage(self, value: str) -> "MonitorBuilder":
        self._data["kafkaProducerMessage"] = value
        return self

    def kafkaProducerSsl(self, value: bool) -> "MonitorBuilder":
        self._data["kafkaProducerSsl"] = value
        return self

    def kafkaProducerAllowAutoTopicCreation(self, value: bool) -> "MonitorBuilder":
        self._data["kafkaProducerAllowAutoTopicCreation"] = value
        return self

    def kafkaProducerSaslOptions(self, value: dict) -> "MonitorBuilder":
        self._data["kafkaProducerSaslOptions"] = value
        return self

    # ── v2 HTTP params ───────────────────────────────────────────────────

    def cacheBust(self, value: bool) -> "MonitorBuilder":
        self._data["cacheBust"] = value
        return self

    def retryOnlyOnStatusCodeFailure(self, value: bool) -> "MonitorBuilder":
        self._data["retryOnlyOnStatusCodeFailure"] = value
        return self

    def bearer_token(self, value: str) -> "MonitorBuilder":
        self._data["bearer_token"] = value
        return self

    def oauth_audience(self, value: str) -> "MonitorBuilder":
        self._data["oauth_audience"] = value
        return self

    def domainExpiryNotification(self, value: bool) -> "MonitorBuilder":
        self._data["domainExpiryNotification"] = value
        return self

    def saveResponse(self, value: bool) -> "MonitorBuilder":
        self._data["saveResponse"] = value
        return self

    def saveErrorResponse(self, value: bool) -> "MonitorBuilder":
        self._data["saveErrorResponse"] = value
        return self

    def responseMaxLength(self, value: int) -> "MonitorBuilder":
        self._data["responseMaxLength"] = value
        return self

    def responsecheck(self, value: str) -> "MonitorBuilder":
        self._data["responsecheck"] = value
        return self

    # ── v2 Network ───────────────────────────────────────────────────────

    def ipFamily(self, value: str) -> "MonitorBuilder":
        self._data["ipFamily"] = value
        return self

    # ── v2 PING ──────────────────────────────────────────────────────────

    def ping_count(self, value: int) -> "MonitorBuilder":
        self._data["ping_count"] = value
        return self

    def ping_numeric(self, value: bool) -> "MonitorBuilder":
        self._data["ping_numeric"] = value
        return self

    def ping_per_request_timeout(self, value: int) -> "MonitorBuilder":
        self._data["ping_per_request_timeout"] = value
        return self

    # ── v2 Misc / low-priority ───────────────────────────────────────────

    def subtype(self, value: str) -> "MonitorBuilder":
        self._data["subtype"] = value
        return self

    def wsSubprotocol(self, value: str) -> "MonitorBuilder":
        self._data["wsSubprotocol"] = value
        return self

    def wsIgnoreSecWebsocketAcceptHeader(self, value: bool) -> "MonitorBuilder":
        self._data["wsIgnoreSecWebsocketAcceptHeader"] = value
        return self

    def remoteBrowsersToggle(self, value: bool) -> "MonitorBuilder":
        self._data["remoteBrowsersToggle"] = value
        return self

    def remote_browser(self, value: str) -> "MonitorBuilder":
        self._data["remote_browser"] = value
        return self

    def screenshot_delay(self, value: int) -> "MonitorBuilder":
        self._data["screenshot_delay"] = value
        return self

    def protocol(self, value: str) -> "MonitorBuilder":
        self._data["protocol"] = value
        return self

    # ── RABBITMQ ─────────────────────────────────────────────────────────

    def rabbitmqNodes(self, value: list) -> "MonitorBuilder":
        self._data["rabbitmqNodes"] = value
        return self

    def rabbitmqUsername(self, value: str) -> "MonitorBuilder":
        self._data["rabbitmqUsername"] = value
        return self

    def rabbitmqPassword(self, value: str) -> "MonitorBuilder":
        self._data["rabbitmqPassword"] = value
        return self

    # ── SNMP ─────────────────────────────────────────────────────────────

    def snmpOid(self, value: str) -> "MonitorBuilder":
        self._data["snmpOid"] = value
        return self

    def snmpVersion(self, value: str) -> "MonitorBuilder":
        self._data["snmpVersion"] = value
        return self

    def snmp_v3_username(self, value: str) -> "MonitorBuilder":
        self._data["snmp_v3_username"] = value
        return self

    # ── SMTP ─────────────────────────────────────────────────────────────

    def smtpSecurity(self, value: str) -> "MonitorBuilder":
        self._data["smtpSecurity"] = value
        return self

    # ── SYSTEM_SERVICE ───────────────────────────────────────────────────

    def system_service_name(self, value: str) -> "MonitorBuilder":
        self._data["system_service_name"] = value
        return self

    # ── Build ────────────────────────────────────────────────────────────

    def build(self) -> dict:
        """Build the monitor configuration dictionary.

        Returns a dict containing only explicitly-set fields, suitable for
        passing to ``add_monitor(**builder.build())`` or
        ``edit_monitor(id_, **builder.build())``.

        Raises:
            ValueError: If ``type`` or ``name`` have not been set.
        """
        missing = []
        if "type" not in self._data:
            missing.append("type")
        if "name" not in self._data:
            missing.append("name")
        if missing:
            raise ValueError(f"Required fields not set: {', '.join(missing)}")
        return dict(self._data)

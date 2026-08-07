# Requirements Document

## Introduction

The Library treats v2-only monitor fields two different ways when the connected
server predates Uptime Kuma 2.0. `conditions` raises `UptimeKumaException`. The
other 25 gated field names are omitted from the payload with no signal of any
kind. Each half was decided on its own merits and each is defensible in
isolation, but a caller cannot tell from the outside which half a given field
falls into, and every future gated field currently arrives as a fresh judgement
call.

This feature replaces the two behaviours with **one rule for the whole class**,
and answers the three questions issue #14 poses:

1. What happens to a v2-only value the server cannot accept.
2. How the caller finds out it happened.
3. Where that behaviour is documented.

It is a policy decision rather than a defect fix. There is no broken behaviour to
reproduce: both current halves work as designed, and both are documented in the
CHANGELOG. What is missing is predictability across the class.

**All six decisions have been ratified by the maintainer.** They are recorded
with their rationale and accepted cost in
[Ratified Decisions](#ratified-decisions), and the order in which the ratified
work lands is recorded in [Sequencing](#sequencing). No acceptance criterion in
this document is conditional on an unsettled decision. Two of the six were
settled by moving work out of this spec: decision 6 assigns PEP 440 pre-release
comparison to a separate fix to `_parsed_version()` that lands first, and
decision 5 narrows the class to monitor fields with a follow-up issue for the
un-inventoried v2-only surfaces.

## Glossary

- **Library**: The `uptime_kuma_api` package, specifically `UptimeKumaApi` in
  `uptime_kuma_api/api.py`.
- **Server_Version**: The version string the connected Uptime Kuma server
  reports via the `info` event, exposed as the `version` property and parsed for
  comparison by `_parsed_version()`.
- **Version_Floor**: The lowest Server_Version at which a given field is
  implemented by the server. For every field currently gated, the Version_Floor
  is `2.0`.
- **V2_Only_Field**: A monitor field the Library sends only when
  `_parsed_version()` is at or above that field's Version_Floor. There are 26
  such field names today, enumerated in
  [The class as it stands](#the-class-as-it-stands).
- **Withheld**: A V2_Only_Field that the caller supplied a value for and that
  the Library left out of the payload because the Server_Version is below the
  field's Version_Floor.
- **Outcome_Rule**: The single behaviour this feature defines for a
  caller-supplied V2_Only_Field when the Server_Version is below that field's
  Version_Floor. Ratified by decision 1 as: withhold the field from the payload
  and emit a Signal. `conditions` is the one named exception, ratified by
  decision 2.
- **Field_Registry**: A single private, module-level mapping from V2_Only_Field
  name to that field's Version_Floor and to the monitor types the field applies
  to, ratified by decision 4. It holds data only and replaces no control flow
  outside the 26 V2_Only_Field names.
- **Signal**: The caller-observable notification that a V2_Only_Field was
  Withheld, ratified by decision 3 as one `warnings.warn` call carrying the
  Warning_Category. Silence is the absence of a Signal.
- **Warning_Category**: The dedicated warning class this feature adds,
  subclassing a standard library warning category so that callers can filter on
  it, exported from `uptime_kuma_api/__init__.py` and documented in
  `docs/api.rst`. The design selects its final name.
- **Version_Comparison_Fix**: The separate change to `_parsed_version()`, filed
  as **issue #30**, that covers PEP 440 release-segment comparison, `None` and
  empty Server_Version handling, and the `TypeError` that the existing
  `except InvalidVersion` does not catch. Ratified by decision 6 as out of scope
  here and as landing before this feature.
- **Type_Gate**: `_check_monitor_type_supported`, shipped in 2.3.1 via PR #21,
  which rejects the four v2-only monitor types (`RABBITMQ`, `SNMP`, `SMTP`,
  `SYSTEM_SERVICE`) on a pre-2.0 server before any payload is built.
- **Reachable_On_V1**: A V2_Only_Field that a caller can still supply on a
  pre-2.0 server after the Type_Gate has run, because the field belongs to a
  monitor type the server implements.
- **Verification_Run**: A manual run against a disposable Uptime Kuma 1.23.x
  container that records, per V2_Only_Field, whether the server accepts or
  rejects a payload carrying that field. It runs before the Outcome_Rule is
  implemented, so that a field the v1 server accepts is removed from the
  Field_Registry rather than gated by it.

## The class as it stands

Verified by reading `uptime_kuma_api/api.py` at version 2.3.1. The workspace
grep tool returns false negatives on that file; every statement below comes from
reading it directly.

26 field names sit behind a version comparison. 25 are silent-only. `conditions`
is the 26th and is the only one with two behaviours.

| Group | Fields | Current behaviour on a pre-2.0 server |
|---|---|---|
| `conditions` | `conditions` | Raises `UptimeKumaException` when truthy; omitted silently when absent or falsy |
| Network | `ipFamily` | Omitted silently |
| HTTP set | `cacheBust`, `retryOnlyOnStatusCodeFailure`, `bearer_token`, `oauth_audience`, `domainExpiryNotification`, `saveResponse`, `saveErrorResponse`, `responseMaxLength`, `responsecheck` | Omitted silently |
| Low-priority set, not type-gated | `subtype`, `wsSubprotocol`, `wsIgnoreSecWebsocketAcceptHeader`, `remoteBrowsersToggle`, `remote_browser`, `screenshot_delay`, `gamedigToken`, `protocol` | Omitted silently |
| Gated in place, inside type blocks | `jsonPathOperator` (JSON_QUERY), `snmp_v3_username` (SNMP), `ping_count` / `ping_numeric` / `ping_per_request_timeout` (PING), `mqttWebsocketPath` / `mqttCheckType` (MQTT) | Omitted silently |

Three properties of this set bear on the requirements:

- **The Type_Gate has already shrunk the v1 surface.** The companion fields of
  `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE` are unreachable on a pre-2.0
  server, because the type is rejected before a payload is built. Of the 26
  names, exactly one — `snmp_v3_username` — belongs solely to a v2-only type and
  is therefore not Reachable_On_V1. It is dead code on v1 and is the one member
  of the class the Outcome_Rule provably cannot affect. `ipFamily` is gated to a
  type list that includes v2-only types **and** types present on both majors, so
  it stays Reachable_On_V1.
- **An explicit `conditions=[]` is not a request.** The guard tests truthiness,
  not `is not None`, so an empty list is omitted rather than rejected.
- **Whether the server rejects each of the other 25 is unverified.** No
  Verification_Run has been performed for them. With decision 1 ratified this is
  no longer an objection to a blanket raise — nothing blanket-raises — but it is
  the reason requirement 7 still exists: a field the v1 server accepts is not
  genuinely v2-only, and belongs out of the Field_Registry rather than in it.

## Requirements

### Requirement 1: One outcome for the whole class

**User Story:** As a caller automating Uptime Kuma across a mixed fleet, I want
every v2-only monitor field to behave the same way on an older server, so that I
can predict what happens without consulting a per-field table.

#### Acceptance Criteria

1. WHEN a caller supplies a value other than `None` for a V2_Only_Field and the
   Server_Version is below that field's Version_Floor, THE Library SHALL apply
   the Outcome_Rule to that field, withholding the field from the payload and
   emitting the Signal required by requirement 2.
2. THE Library SHALL apply the same Outcome_Rule to each of the 25
   Reachable_On_V1 V2_Only_Field names — every one of the 26 V2_Only_Field names
   except `snmp_v3_username`, which no caller can reach on a pre-2.0 server
   because the Type_Gate rejects the `SNMP` monitor type before a payload is
   built.
3. THE Library documentation SHALL name `conditions` as the single exception to
   the Outcome_Rule, state that a truthy `conditions` value raises
   `UptimeKumaException` on a Server_Version below `2.0` rather than being
   Withheld, and state that the reason is that `conditions` changes the
   monitor's up/down verdict, in the single location required by requirement
   3.1.
4. THE Library documentation SHALL state the test that decides which behaviour a
   V2_Only_Field receives — a field that changes the monitor's verdict raises, a
   field that changes how the check runs is Withheld with a Signal — in the
   single location required by requirement 3.1, so that a later field inherits a
   criterion rather than arguing from precedent.
5. WHEN a V2_Only_Field is added to the Library after the Outcome_Rule is
   ratified and that field is not named as an exception under criterion 3, THE
   Library SHALL apply the Outcome_Rule to that field at every Server_Version
   below the field's Version_Floor.
6. THE Outcome_Rule SHALL govern every monitor field accepted by
   `_build_monitor_data` and by `edit_monitor`, and THE Library SHALL leave every
   v2-only surface outside that boundary — status pages, maintenance and settings
   — behaving as version 2.3.1 behaves.
7. THE Library documentation SHALL state the Outcome_Rule as a rule about
   v2-only fields rather than as a rule about the 26 field names it governs
   today, so that extending the rule to a further v2-only surface is the addition
   of Field_Registry entries rather than the ratification of a new policy.
8. WHEN a caller requests one of the four v2-only monitor types (`RABBITMQ`,
   `SNMP`, `SMTP`, `SYSTEM_SERVICE`) on a Server_Version below 2.0, THE Library
   SHALL continue to reject the call through the Type_Gate before building any
   payload, because a monitor type is outside this feature's class boundary.
9. THE Library SHALL leave the exception class raised by the Type_Gate and the
   message that exception carries unchanged from version 2.3.1.
10. WHEN a caller supplies a V2_Only_Field value that is falsy but not `None`
    (for example an empty list) and the Server_Version is below that field's
    Version_Floor, THE Library SHALL apply the same Outcome_Rule it applies to a
    truthy supplied value for that field, except for `conditions`, whose
    truthiness test is verified existing behaviour and is preserved by
    requirement 2.4.
11. IF a call supplies no V2_Only_Field, or supplies `None` for every
    V2_Only_Field it names, THEN THE Library SHALL build the payload version
    2.3.1 builds for that call, SHALL apply no part of the Outcome_Rule, and
    SHALL raise no exception.

### Requirement 2: The caller finds out

**User Story:** As a caller, I want to learn that a field I supplied was not
sent, so that I can decide whether the monitor the server created is the monitor
I asked for.

#### Acceptance Criteria

1. WHEN a single call withholds one or more V2_Only_Fields, THE Library SHALL
   emit exactly one Signal for that call through `warnings.warn` carrying the
   Warning_Category, and THE Signal SHALL carry the caller-facing parameter name
   of every withheld field as the caller passed it together with each withheld
   field's Version_Floor. (One Signal per call rather than one per withheld
   field, so a call withholding six fields is one notification and not six.)
2. WHEN the Library withholds a V2_Only_Field, THE Signal SHALL state the
   Server_Version that the `version` property reports for the connected server.
3. WHEN a single call withholds more than one V2_Only_Field, THE Library SHALL
   name every withheld field in that call's Signal, and THE Signal SHALL NOT
   name a V2_Only_Field that the call sent.
4. IF a call supplies no V2_Only_Field — every V2_Only_Field parameter other than
   `conditions` is absent or `None`, and `conditions` is absent, `None` or an
   empty list — THEN THE Library SHALL emit no Signal. (The `conditions` clause is
   verified behaviour rather than a choice: the guard tests truthiness, so an
   empty list is treated as no request today. This keeps the default
   `add_monitor` path silent, which is what makes a Signal usable rather than
   noise.)
5. WHERE a caller supplies a truthy `conditions` value and the Server_Version is
   below `2.0`, THE Library SHALL raise `UptimeKumaException` before making any
   server call, SHALL create no monitor and modify no monitor, SHALL emit no
   Signal for that call, and SHALL leave every object the caller passed as an
   argument unmodified. (This preserves the property the `conditions` guard
   already holds: no `getMonitor` round trip is spent on a call that fails.)
6. WHEN the Server_Version is at or above the Version_Floor of every
   V2_Only_Field a call supplies, THE Library SHALL emit no Signal for that call.
   (Criterion 4 covers only the call that supplies no V2_Only_Field, which leaves
   the nominal 2.x path — fields supplied and supported — otherwise uncovered.)
7. WHEN a call withholds one or more V2_Only_Fields, THE Library SHALL return the
   value and the return-value key set that version 2.3.1 returns for the same
   call, and SHALL emit the Signal before sending the payload to the server.
8. WHEN a caller supplies a V2_Only_Field value that is falsy but not `None` —
   for example `saveResponse=False` — and the Server_Version is below that
   field's Version_Floor, THE Library SHALL treat that field as Withheld for the
   purposes of criteria 1 to 3. `conditions` is excluded from this criterion,
   because its truthiness test is verified existing behaviour.
9. THE Library SHALL define the Warning_Category as a subclass of a standard
   library warning category, SHALL export it from `uptime_kuma_api/__init__.py`,
   and SHALL add it to `docs/api.rst`. (Verified by reading the package:
   `warnings` is imported nowhere, so the `warnings.warn` carrier is new
   machinery; `logging` is already imported, function-locally in
   `UptimeKumaApi.__init__`, to type-check the `logger` parameter forwarded to
   `socketio.Client`, so it is not new machinery in the same sense — but that
   logger is the caller's, for socketio's own output, not a library logger for
   the Library's own messages. If 7.11's fallback is taken and the Signal moves
   to `logging`, the class would carry two unrelated logger concepts; the
   fallback stays viable but is not free. The only exception classes remain
   `UptimeKumaException` and `Timeout`. Sphinx autodoc has no discovery
   mechanism and emits no warning for an omitted export, so the `docs/api.rst`
   half cannot be left to a later pass.)
10. WHEN a caller has configured `warnings.simplefilter("error", …)` for the
    Warning_Category and a call would withhold a V2_Only_Field, THE Library SHALL
    let the resulting exception reach the caller, and SHALL send no payload for
    that call. (This is the decisive property of decision 3: raise-for-all
    behaviour is available opt-in without the Library imposing it on anyone, and
    it holds only because criterion 7 requires the Signal before the server
    call.)

### Requirement 3: The rule is documented in one place

**User Story:** As a contributor adding the next gated field, I want one
authoritative statement of the rule, so that I inherit a decision instead of
making a new one.

#### Acceptance Criteria

1. THE Library documentation SHALL state the Outcome_Rule in exactly one
   normative location, which SHALL be either a docstring in
   `uptime_kuma_api/api.py` that Sphinx autodoc renders under the
   `UptimeKumaApi` entry of `docs/api.rst`, or prose added to `docs/api.rst`
   itself. (Verified: `docs/api.rst` holds a `Main Interface` section carrying
   `.. autoclass:: UptimeKumaApi`, and `docs/conf.py` enables only
   `sphinx.ext.autodoc` with `autodoc_member_order = "bysource"`. `docs/api.rst`
   is the only published page that documents the API — the others are
   `docs/index.rst` and `docs/install.rst` — and it carries no narrative section
   for monitor fields, so those two are the locations this project actually has.)
2. THE `add_monitor` and `edit_monitor` docstrings SHALL each carry a
   cross-reference to the single normative location required by criterion 1, and
   SHALL NOT restate the Outcome_Rule as a second normative statement, because
   two normative copies drifting apart is this project's recurring failure mode.
3. THE `CHANGELOG.md` entry for this change SHALL appear under the release
   heading of the version that ships it, SHALL state the Outcome_Rule, SHALL name
   every field whose behaviour changes, and SHALL state, for each named field,
   what a caller relying on the previous behaviour observes instead.
4. THE Library SHALL record in
   `.kiro/specs/uptime-kuma-v2-support-backlog/requirements.md`, against
   requirement 13.3, that this feature further narrows 13.3 by adding a warning
   that 13.3 forbids, SHALL quote the phrase `without raising an error or logging
   a warning` that the record addresses, and SHALL state the reason for the
   reversal — 13.3 rested on the premise that a dropped field fails observably,
   and the issue #12 verification falsified that premise for a whole subclass of
   fields. (13.3 already carries a NARROWED annotation from
   `conditions-field-v1-regression`; this criterion extends that annotation
   rather than creating one.)
5. THE Library SHALL record in the `## Cross-Spec Policy Conflict` section of
   `.kiro/specs/conditions-field-v1-regression/design.md` that the `conditions`
   raise is retained as the single named exception to the Outcome_Rule and that
   the test in requirement 1.4 is what justifies it, because that section is
   where the raise's severity justification is held.
6. THE single normative location required by criterion 1 SHALL state which class
   of monitor fields the Outcome_Rule governs, where a caller finds each field's
   Version_Floor, how a caller learns that a field was Withheld, the name of the
   Warning_Category a caller filters on, and every field named as an exception
   under requirement 1.3.
7. THE change that introduces the Outcome_Rule SHALL carry the normative
   location, the two docstring cross-references and the `CHANGELOG.md` entry in
   the same merged change, because a documentation half left to a later pass is
   how the two-copy drift starts.
8. WHEN the documentation is built with `make html` (`docs/make.bat html` on
   Windows), THE build SHALL render the normative location and resolve every
   cross-reference to it without emitting a Sphinx warning.

### Requirement 4: One source of truth for the field set

**User Story:** As a contributor, I want the gated fields and their version
floors held in one place, so that adding a field is a data change rather than a
new control-flow branch.

#### Acceptance Criteria

1. THE Library SHALL hold all V2_Only_Field names confirmed by the
   Verification_Run in a single Field_Registry, each entry mapping a field name
   to that field's Version_Floor, and SHALL perform no version comparison for any
   registry field outside the Field_Registry. (Verified split today: 19 of the 26
   sit inside the single `>= 2.0` block near the end of `_build_monitor_data` —
   `conditions`, `ipFamily`, the 9 HTTP fields and the 8 low-priority fields —
   and the remaining 7 are gated in place inside their own monitor-type blocks.
   The entry count is 26 less any field the Verification_Run shows the v1 server
   accepts, per requirement 7.)
2. WHEN the Library decides whether to include a V2_Only_Field in a payload, THE
   Library SHALL decide solely by comparing `self._parsed_version()` against that
   field's Version_Floor as read from the Field_Registry, subject to the type
   restriction required by criterion 4.
3. THE Field_Registry SHALL be a module-level name in `uptime_kuma_api/api.py`
   beginning with a single underscore, and SHALL be absent from
   `dir(uptime_kuma_api)`, from `uptime_kuma_api.__all__` and from
   `docs/api.rst`, following the precedent of `_V2_ONLY_MONITOR_TYPES`, whose
   absence `tests/test_monitor_params_v2.py` already asserts in exactly this
   form.
4. WHERE a V2_Only_Field applies only to specific monitor types, THE
   Field_Registry entry for that field SHALL record the set of monitor types the
   field applies to. (`ipFamily` is restricted to a list of 14 types, the 9 HTTP
   fields to 4 types, and each of the 7 in-place fields to a single type; the 8
   low-priority fields carry no type restriction. A registry keyed on field name
   alone would emit the restricted ones for every type.)
5. WHERE a Field_Registry entry records a monitor-type set, THE Library SHALL
   omit that field from the payload for every monitor type outside that set, at
   every Server_Version.
6. WHEN a V2_Only_Field is added to the Field_Registry, THE Library SHALL gate
   that field from its registry entry alone and SHALL add no version comparison
   to `_build_monitor_data` for it, so that adding a field is a data change.
7. THE Library SHALL leave every monitor field absent from the Field_Registry
   gated exactly as version 2.3.1 gates it, including the `1.22` comparison on
   `parent`, the `1.23` comparisons on `invertKeyword`, `timeout` and
   `gamedigGivenPortOnly`, and the `1.23.1` comparison in `set_settings`, because
   the Field_Registry is scoped to the V2_Only_Field data and is not a rewrite of
   `_build_monitor_data`. (Consistent with requirement 5.4.)
8. THE Field_Registry SHALL hold the mapping shape field name to Version_Floor,
   so that issue #28's per-monitor-type floor map can adopt the same shape and
   the pre-release comparison is written once, and THE Library SHALL keep the two
   structures separate rather than merging the field map and the type map.
9. WHEN the Library withholds one or more V2_Only_Fields for a call, THE Library
   SHALL enumerate the withheld fields from the Field_Registry in a single pass,
   so that the Signal required by requirement 2.1 names every withheld field
   without a per-field branch.

### Requirement 5: Version comparison is correct at the boundary

**User Story:** As a caller running a pre-release server, I want a field the
Library gates at a given version to work on the pre-release that introduced it,
so that a release-candidate deployment is not treated as older than it is.

**Dependency, not a requirement of this feature.** Decision 6 assigns PEP 440
pre-release comparison, `None` and empty Server_Version handling, and the
escaping `TypeError` to the Version_Comparison_Fix — filed as **issue #30** —
which is a correctness fix to `_parsed_version()` and lands before this feature. That fix, not this one,
establishes what `2.0.0b1`, `2.0.0rc1`, `2.0.0.dev1`, `2.0.0.post1`, `None` and
`""` mean against a Version_Floor. This spec's correctness at a pre-release
Server_Version is **inherited** from that fix rather than established here:
verified against the installed `packaging`, `2.0.0b1 < 2.0` is true, so a 2.0
beta server is misclassified as v1 by every gate in the Library today. Two
clarifications #30 establishes, both stronger than the weaker form of the claim:
the misclassification is **not** confined to the `2.0` boundary — `1.23.0-beta.1`,
a real Uptime Kuma tag whose `package.json` version equals the tag name, parses
to `1.23.0b1` and is treated as below `1.23`, so it also misses the `1.23` gates
on `invertKeyword`, `timeout` and `gamedigGivenPortOnly` — and these strings do
**not** reach the `9999` sentinel, since `2.0.0-beta.4` parses successfully to
`2.0.0b4` and is therefore misclassified rather than treated as newest.
Separately, `parse_version(None)` raises `TypeError`, which the
`except InvalidVersion` in `_parsed_version()` does not catch. The criteria below
are the part this feature owns.

#### Acceptance Criteria

1. THE Library SHALL obtain the Server_Version for comparison through
   `self._parsed_version()`, SHALL compare it against a Version_Floor parsed by
   `parse_version`, and SHALL leave `self.version` parsed by no other route,
   because a second parsing route is a second place for the boundary rule to
   diverge.
2. WHEN the Server_Version equals a field's Version_Floor, THE Library SHALL
   treat the server as implementing that field, so that a server reporting `2.0`
   is treated as implementing a field floored at `2.0` while a server reporting
   `1.23.2` is not.
3. IF the Server_Version is unparseable, THEN THE Library SHALL treat the server
   as at or above every Version_Floor, preserving the `9999` sentinel behaviour
   of `_parsed_version()`, and SHALL let no exception raised while parsing reach
   the caller.
4. THE Library SHALL produce, for every final-release Server_Version in the
   supported 1.21.3 through 2.5.0 range and for every monitor field absent from
   the Field_Registry, the same gate outcome and the same payload as version
   2.3.1 produces at that Server_Version, including at the `1.22`, `1.23`,
   `1.23.1` and `2.0` comparison boundaries.
5. WHERE the Server_Version carries a PEP 440 pre-release, dev-release,
   post-release or local-version segment, THE Library SHALL obtain its verdict
   from `self._parsed_version()` alone, so that the semantics the
   Version_Comparison_Fix establishes apply unchanged to every Version_Floor in
   the Field_Registry and this feature adds no second pre-release rule.
6. IF the Server_Version is `None` or an empty string, THEN THE Library SHALL
   obtain its verdict from `self._parsed_version()` alone and SHALL add no
   handling of its own for those two values, because the Version_Comparison_Fix
   owns them.
7. THE Library SHALL depend on the Version_Comparison_Fix landing before this
   feature, and THE design document for this feature SHALL state that a
   pre-release Server_Version is gated correctly only once that fix has landed.

### Requirement 6: Behaviour on Uptime Kuma 2.x is unchanged

**User Story:** As a caller on a 2.x server, I want this change to be invisible,
so that upgrading the Library carries no risk for me.

#### Acceptance Criteria

1. WHEN the Server_Version is at or above a field's Version_Floor, THE Library
   SHALL place that field in the payload under the same key, holding a value
   equal to the value version 2.3.1 places there, for identical arguments at the
   same mocked Server_Version.
2. WHEN a caller supplies a `conditions` list on a server at or above 2.0, THE
   Library SHALL place the caller's own list object in the payload — the same
   object by identity, neither copied, reordered nor mutated — for a non-empty
   list and for an empty list alike.
3. WHEN a caller supplies `conditions=None` on a server at or above 2.0, THE
   Library SHALL place an empty list in the payload, so that the payload key set
   and the value at `conditions` equal those produced for an explicit
   `conditions=[]`. (Criteria 2 and 3 together are what make a
   `conditions if conditions else list()` form detectable by test: that form
   allocates a fresh list for a falsy empty list, breaking the identity criterion
   2 requires.)
4. IF a caller supplies a `conditions` value that is neither a list nor `None`,
   THEN THE Library SHALL raise `TypeError` carrying the message `conditions must
   be a list or None`, SHALL raise an exception that is not an instance of
   `UptimeKumaException`, and SHALL raise before comparing the Server_Version
   against any Version_Floor, before the Type_Gate runs and before making any
   server call, at a mocked Server_Version of `1.23.1` and at a mocked
   Server_Version of `2.4.0` alike.
5. WHEN the Server_Version is at or above a field's Version_Floor and a caller
   supplies a value for that field, THE Library SHALL raise no exception, SHALL
   emit no `warnings` warning and SHALL emit no log record at level WARNING or
   above. (Requirement 2.4 covers only the call that supplies no V2_Only_Field,
   so the supported-and-supplied path needs its own silence criterion.)
6. THE Library SHALL produce, for each monitor field absent from the
   Field_Registry and at each Server_Version, the same payload key presence and
   the same value as version 2.3.1 produces at that Server_Version, on the
   `add_monitor` path and on the `edit_monitor` merge path alike. (Stated per
   version rather than as sameness across the two majors on purpose: `parent` is
   gated at `1.22` and `timeout` at `1.23`, so a field outside the
   Field_Registry legitimately differs between a 1.21.3 server and a 2.x one.)
7. THE Library SHALL leave `MonitorBuilder` unchanged in its setter names, its
   setter parameter defaults, the key set `build()` returns for a given sequence
   of setter calls, and which of its fields are required rather than optional
   (`type` and `name`), because the builder holds no server connection and
   therefore cannot know the Server_Version.
8. THE Library SHALL leave the parameter names, parameter defaults and return
   types of `add_monitor` and `edit_monitor` unchanged from version 2.3.1.
9. THE Library SHALL add the Warning_Category to `uptime_kuma_api/__init__.py`
   and to `docs/api.rst` as this change's one new public name, because
   filterability is the whole point of decision 3 and a category a caller cannot
   import cannot be filtered on.
10. THE Library SHALL add no public name other than the Warning_Category — no
    further export in `uptime_kuma_api/__init__.py` and no further directive in
    `docs/api.rst` — because a new warning message is not public API surface.

### Requirement 7: Mis-gated fields are found by observation before the rule ships

**User Story:** As the maintainer implementing the Outcome_Rule, I want to know
whether a pre-2.0 server actually rejects each gated field, so that a field the
server accepts is corrected out of the Field_Registry rather than being withheld
from callers who could have sent it.

The Outcome_Rule is ratified, so the Verification_Run no longer chooses between
candidates. Its purpose is to detect a **mis-gated** field: a field a 1.23.x
server accepts and round-trips is not genuinely v2-only, and belongs outside the
Field_Registry. The run therefore happens **before** the Outcome_Rule is
implemented, so a corrected field list precedes the code rather than following
it.

#### Acceptance Criteria

1. THE Verification_Run SHALL record, for each of the 25 Reachable_On_V1
   V2_Only_Fields, the monitor type used to exercise the field and exactly one
   verdict from the set `REJECTED` (the server returned an error for the payload
   carrying the field), `ACCEPTED` (the field came back on read-back holding the
   value sent), `ABSENT` (the payload succeeded and the field did not come back)
   and `MISMATCH` (the field came back holding a value other than the one sent).
2. WHEN the Verification_Run records `ACCEPTED` for a V2_Only_Field, THE
   Field_Registry SHALL omit that field, because a field a 1.23.x server accepts
   and returns unchanged is not a V2_Only_Field and gating it would withhold a
   value the server supports.
3. THE Verification_Run SHALL complete and its per-field results SHALL be
   recorded before the change implementing the Outcome_Rule is opened for
   review, so that the Field_Registry is built from the corrected field list.
4. THE Verification_Run SHALL target a disposable Uptime Kuma 1.23.x container
   addressed through its own `UPTIME_KUMA_V1_URL`, `UPTIME_KUMA_V1_USERNAME` and
   `UPTIME_KUMA_V1_PASSWORD` keys rather than the 2.x `tests/.env` keys, and
   SHALL confirm the reported Server_Version begins with `1.23` before sending
   any monitor payload.
5. IF the target URL is unset, or the reported Server_Version does not begin with
   `1.23`, THEN THE Verification_Run SHALL send no monitor payload, SHALL create
   no monitor, and SHALL exit reporting `FAIL` with an indication that the target
   was not confirmed to be a 1.23.x server.
6. WHEN the server has accepted a payload carrying a V2_Only_Field, THE
   Verification_Run SHALL read that monitor back and SHALL compare every field
   sent against the value returned, reporting `PASS` for a field whose returned
   value equals the value sent and `FAIL` for a field that is `ABSENT` or
   `MISMATCH`.
7. WHEN the Verification_Run has created a monitor, THE Verification_Run SHALL
   delete that monitor before exiting, including on the path where sending or
   reading back a field raised an exception.
8. WHERE the Verification_Run is scripted, THE script output SHALL contain only
   characters in the ASCII range (code points 0 to 127), using `PASS`, `FAIL` and
   `->` as its status markers.
9. THE Verification_Run SHALL record its per-field results in a file in this
   spec's directory stating the observed Server_Version, the date of the run, and
   one verdict per field, and SHALL refer to the container host, the SSH user and
   any credential only through the `<docker-host>` and `<user>` placeholders.
10. IF a Reachable_On_V1 V2_Only_Field was not exercised during the
    Verification_Run, THEN THE recorded results SHALL name that field with a
    not-observed verdict rather than omitting it, so that an incomplete run is
    visible as incomplete.
11. THE maintainer SHALL confirm, before the change carrying the Warning_Category
    is merged, how the companion Ansible collection handles unexpected output on
    stderr from a module, and SHALL record the observed behaviour alongside the
    Verification_Run results. (`warnings.warn` writes to stderr by default. If
    warnings pollute module output, `logging` is the ratified fallback carrier,
    in which case every other part of decision 3's reasoning survives except
    filterability.)

### Requirement 8: The change is covered by the unit suite

**User Story:** As a maintainer, I want the rule pinned by tests on both server
majors, so that a later contributor who disagrees with it fails a test rather
than silently reverting it.

#### Acceptance Criteria

1. THE Library tests for this change SHALL live in
   `tests/test_monitor_params_v2.py`, alongside the existing gate classes.
2. THE Library tests SHALL add no new test file, because the file the tests join
   is already collected by a bare `pytest`.
3. THE Library tests SHALL assert the Outcome_Rule at a mocked Server_Version of
   `1.23.2` and at a mocked Server_Version of `2.4.0` — the two the file already
   uses — for at least one Reachable_On_V1 V2_Only_Field drawn from each of the
   five groups in the table in
   [The class as it stands](#the-class-as-it-stands), excluding
   `snmp_v3_username`, which is not Reachable_On_V1.
4. WHEN the Library withholds a V2_Only_Field, THE Library tests SHALL assert
   that exactly one warning of the Warning_Category is emitted and that the
   warning names the withheld field, the field's Version_Floor and the observed
   Server_Version.
5. WHEN the Library withholds a V2_Only_Field, THE Library tests SHALL assert
   that no exception is raised for that field, that the field's key is absent
   from the payload, and that every non-gated field the call supplied is present
   in the payload holding the value supplied, so that a later change adding an
   exception or dropping a supported field fails a test.
6. WHEN a caller supplies a truthy `conditions` value at a mocked Server_Version
   of `1.23.2`, THE Library tests SHALL assert that `UptimeKumaException` is
   raised, that no server call is made, and that no warning of the
   Warning_Category is emitted, so that the one named exception to the
   Outcome_Rule is pinned as an exception rather than drifting into the general
   rule.
7. WHERE a caller has configured `warnings.simplefilter("error", …)` for the
   Warning_Category, THE Library tests SHALL assert that a call which would
   withhold a V2_Only_Field raises instead and sends no payload.
8. THE Library tests SHALL assert that a call supplying no V2_Only_Field raises no
   exception, emits no `warnings` warning, emits no log record at level WARNING or
   above, and adds no key to the return value.
9. THE Library tests SHALL leave the existing `TestValidVersionGatePreservation`
   and `TestUnparseableVersionBugCondition` classes unmodified, and both classes
   SHALL pass in the same `pytest` run as the tests added for this change, because
   an unmodified class that is never run proves nothing.
10. THE Library tests SHALL reach no live server and open no network connection
    during collection or execution, constructing the object under test as a
    `MagicMock(spec=UptimeKumaApi)` with `version` set to the mocked
    Server_Version and the real `UptimeKumaApi._parsed_version` and
    `UptimeKumaApi._build_monitor_data` bound onto it, following the construction
    the existing classes in the file already use.
11. THE Library tests SHALL fail when run against version 2.3.1 behaviour, so that
    a test which has only ever passed does not stand as the evidence for the
    Outcome_Rule.
12. WHERE the Library tests generate inputs, THE tests SHALL generate them from a
    fixed seed following the `PBT_SEED` / `PBT_CASES` idiom already in the file
    rather than through `hypothesis`, which is not a project dependency, and THE
    test output SHALL contain only characters in the ASCII range.

### Requirement 9: Uptime Kuma v1.x keeps working

**User Story:** As a caller on Uptime Kuma 1.x, I want the Library to keep
managing monitors, so that a rule about fields my server does not have does not
cost me the fields it does have.

#### Acceptance Criteria

1. WHEN a caller calls `add_monitor` supplying no V2_Only_Field, THE Library SHALL
   build a payload whose key set equals and whose per-key values equal those of
   the payload version 2.3.1 builds for the same arguments, SHALL issue exactly
   one `add` server call, and SHALL raise no exception, at each of the mocked
   Server_Versions `1.21.3`, `1.22.0` and `1.23.1`. (Three versions rather than
   one: `1.21.3` exercises the pre-`1.22` payload path, `1.22.0` the `parent`
   boundary, `1.23.1` the late-v1 path.)
2. WHEN a caller calls `edit_monitor` against a Server_Version below `2.0`
   supplying no V2_Only_Field, THE Library SHALL issue exactly one `get_monitor`
   call and exactly one `editMonitor` server call, SHALL send a payload whose key
   set equals and whose per-key values equal those version 2.3.1 sends for the
   same arguments, and SHALL let the caller's value take precedence over the
   value `get_monitor` returned for every key the caller supplied.
3. WHERE a caller supplies `conditions` on the `edit_monitor` path, THE Library
   SHALL raise only for a truthy value the caller supplied in the call's own
   keyword arguments, SHALL disregard a `conditions` value present only in the
   `get_monitor` response, and SHALL still issue the `editMonitor` call for a call
   whose only `conditions` value came from that response. (Verified:
   `edit_monitor` runs `self._check_conditions_supported(kwargs.get("conditions"))`
   and `self._check_monitor_type_supported(kwargs.get("type"))` before
   `self.get_monitor(id_)`, so a field the server echoed back is not a request.)
4. THE `CHANGELOG.md` entry for this change SHALL state that the change is
   non-breaking — every call that succeeds against a pre-2.0 server today still
   succeeds and returns the same value, with a warning added — SHALL state that
   `conditions` behaviour is unchanged from version 2.3.1, and SHALL accompany a
   minor version bump recorded as a `feat`.
5. WHEN the Library withholds a V2_Only_Field because the Server_Version is below
   that field's Version_Floor, THE Library SHALL place in the payload every other
   field the caller supplied that the server at that Server_Version supports, so
   that a rule about fields the server does not have costs the caller none of the
   fields it does have.
6. WHERE a caller supplies a truthy `conditions` value on the `edit_monitor` path
   at a Server_Version below `2.0`, THE Library SHALL raise before issuing any
   `editMonitor` call, SHALL leave the monitor as it was before the call, and
   SHALL raise an error indicating that `conditions` requires a Server_Version of
   at least `2.0`. (The error message text itself is deliberately unprescribed,
   and requirement 1.9 keeps the 2.3.1 message intact for the Type_Gate.)
7. THE Library SHALL leave `get_monitor`, `get_monitors`, `pause_monitor`,
   `resume_monitor` and `delete_monitor` behaving on a Server_Version below `2.0`
   as they behave in version 2.3.1, because this feature changes only the fields
   sent on the add and edit paths.

## Ratified Decisions

All six are settled. Each block states what was ratified, why, and what the
decision costs. The candidate-comparison tables that preceded ratification have
been removed; they have served their purpose.

### Decision 1: The Outcome_Rule is withhold plus a Signal

**Ratified.** A caller-supplied V2_Only_Field below its Version_Floor is left out
of the payload and a Signal is emitted. Non-breaking: every call that succeeds
today still succeeds and returns the same value.

**Rationale.** Silent-for-all refuses the issue's second question — how the
caller finds out — which is the hole #14 exists to close. Raise-for-all converts
25 currently-successful calls into failures in order to fix a *predictability*
problem, which is disproportionate and cannot be walked back once shipped.

**Accepted cost.** This narrows `uptime-kuma-v2-support-backlog` requirement
13.3, which forbids even a warning. That is a deliberate reversal, recorded under
requirement 3.4: 13.3 rested on the premise that a dropped field fails
observably, and the issue #12 verification falsified that premise for a whole
subclass of fields — omitting the companion fields of an unsupported type turned
an immediate `SQLITE_ERROR` into a monitor reporting `Added Successfully.` that
then sat `PENDING` indefinitely.

### Decision 2: `conditions` keeps its raise, and the rule states the test

**Ratified.** `conditions` remains the one named exception to the Outcome_Rule.
The rule states the test rather than only the exception, verbatim: *a field that
changes the monitor's verdict raises; a field that changes how the check runs is
withheld with a Signal.*

**Rationale.** #14's complaint is undiscoverability, not the existence of two
behaviours — a documented, named exception is predictable, an undocumented split
is not. Retiring the raise would change behaviour shipped in 2.3.0 and 2.3.1 in
the dangerous direction, from louder to quieter. Stating the test means the next
field inherits a criterion instead of arguing from precedent, and a second
exception must justify itself against a written rule.

**Accepted cost.** The class has two behaviours rather than one, so the
documentation carries both, and the test in requirement 1.4 becomes something a
reviewer has to apply.

### Decision 3: The Signal is `warnings.warn` with a dedicated, exported category

**Ratified.** One `warnings.warn` per call carrying a dedicated Warning_Category
that subclasses a standard warning category, is exported from
`uptime_kuma_api/__init__.py` and is documented in `docs/api.rst`. The design
picks the final name.

**Rationale.** The decisive property: a caller who wants strictness can
`warnings.simplefilter("error", <Category>)` and obtain raise-for-all behaviour
opt-in, without the Library imposing it on anyone. The alternatives lost — a
return key changes the documented return shape of the two most-used methods and
would break round-trip comparison in the companion Ansible collection; an
exception subclass is only meaningful if something raises, which the withhold
path does not; `logging` is semantically wrong for an API-usage mistake and is
not meaningfully quieter, since `logging.lastResort` sends WARNING and above to
stderr when no handler is configured.

**Accepted cost.** Deliberate new public API surface: one export and one
`docs/api.rst` directive, accepted because filterability is the whole point.
Verified by reading `api.py`: `warnings` is imported nowhere in the package, so
the `warnings.warn` carrier is new machinery; `logging`, however, is already
imported — function-locally in `UptimeKumaApi.__init__`, to type-check the
`logger` parameter that is then forwarded to `socketio.Client`. So `logging` is
not new machinery in the same sense, but the logger it already handles is the
caller's, for socketio's own output, not a library logger for the Library's own
messages. Its only exception classes remain `UptimeKumaException` and `Timeout`.
The residual risk — stderr output reaching Ansible module output — is checked by
requirement 7.11, and `logging` is the fallback if it bites; taking that
fallback would leave the class carrying two unrelated logger concepts, the
caller-supplied socketio logger and the Library's own, so the fallback stays
viable but is not free.

### Decision 4: A Field_Registry, scoped to the data only

**Ratified.** A private module-level registry holding field name to
(Version_Floor, applicable monitor types or none), driving a single emission pass
over the registry field names.

**Rationale.** Emitting one Signal per call that names every withheld field
requires something to enumerate what was withheld, so decisions 1, 3 and 4 are
not independent: a Signal without a registry is 26 hand-written branches.

**Accepted cost and boundary.** The registry must NOT become a rewrite of
`_build_monitor_data`. The `1.22` gate on `parent`, the `1.23` gates on
`invertKeyword` / `timeout` / `gamedigGivenPortOnly` and the `1.23.1` gate in
`set_settings` stay exactly as they are (requirement 4.7). The registry shares
the *shape* — name to floor — with issue #28's per-type map without merging the
two structures, so the pre-release comparison is written once (requirement 4.8).

### Decision 5: Monitor fields only, stated explicitly

**Ratified.** The class boundary is the monitor fields accepted by
`_build_monitor_data` and `edit_monitor`. The rule is nonetheless *phrased* about
v2-only fields generally rather than about these 26 names, so that a later
extension is the addition of registry entries rather than the re-ratification of
a policy (requirement 1.7).

**Accepted cost.** The un-inventoried v2-only surfaces — status pages,
maintenance, settings — remain governed by no rule. A follow-up issue covers
them, so this is a tracked narrowing rather than an accidental one.

### Decision 6: Pre-release comparison is settled outside this spec

**Ratified.** The PEP 440 rule belongs to neither #14 nor #28: it is a
correctness fix to `_parsed_version()`, the choke point both depend on. Filed as
**issue #30**, covering release-segment comparison, `None` and empty handling, and
the escaping `TypeError` — `parse_version(None)` raises `TypeError`, which the
existing `except InvalidVersion` does not catch, so a `None` version escapes to
the caller today.

**Rationale.** `2.0.0b1 < 2.0` is true, so a 2.0 beta server is misclassified as
v1 by every gate in the Library today, and `1.23.0-beta.1` is likewise treated as
below `1.23`. Both are real Uptime Kuma tags reporting those exact strings, and
both parse successfully rather than reaching the `9999` sentinel, so they are
misclassified rather than treated as newest. That is a live defect, not a
hypothesis, and it is larger than either issue that surfaced it.

**Accepted cost, and a posture caveat.** Comparing on the release segment alone
means `2.0.0.dev1` — a build from before 2.0 was finished — is treated as
implementing every 2.0 field. That is consistent with the optimistic stance
`_parsed_version()` already takes for an unparseable version, but it is a posture
and not a neutral fix, and it should be recorded as such on the separate issue.

## Sequencing

The ratified order. Each step depends on the one before it.

1. **The `_parsed_version()` Version_Comparison_Fix — issue #30.** Lands first.
   Release-segment comparison, `None` and empty handling, the escaping
   `TypeError`. Requirement 5 depends on it rather than restating it.
2. **The Verification_Run.** Requirement 7. Its results may correct the field
   list, so it precedes the code that consumes that list.
3. **This feature.** The Field_Registry, withhold plus the Warning_Category
   warning, and `conditions` keeping its raise under the written test.
4. **Issue #28.** Consumes the shared floor shape from requirement 4.8 and the
   comparison helper from step 1 for per-monitor-type floors.

## Out of Scope

Referenced rather than resolved.

- **The `_parsed_version()` pre-release and `None`-handling fix — issue #30.**
  Ratified by decision 6 as landing before this feature: release-segment
  comparison for pre-release and dev-release versions; `None` and empty-string
  Server_Version; and the `TypeError` from `parse_version(None)` that the
  existing `except InvalidVersion` does not catch. Post-release and local
  versions are excluded because they already compare correctly —
  `2.0.0.post1 >= 2.0` is true. Requirement 5 states the dependency.
- **The un-inventoried v2-only surfaces.** Decision 5 narrows this feature to
  monitor fields and assigns the rest a follow-up issue, so the narrowing is
  tracked rather than accidental. What that follow-up will find is more specific
  than "governed by no rule", and worth recording now because the loose version
  would send its author looking for an absence:
  - **Status pages already carry a third pattern, and it is one the Outcome_Rule
    could not have absorbed.** `_build_status_page_data` has its own `2.0` gate
    in which `analyticsType`, `analyticsId` and `analyticsScriptUrl` are sent
    **unconditionally, including when `None`**, because the v2 server validates
    `analyticsType` and rejects the entire save with `Invalid analytics type`
    when the key is absent — verified against 2.4.0, where `null` and the three
    named values are accepted while an absent key, `""` and `"none"` are all
    rejected. Omission is therefore not an available outcome for those three
    fields at all. The same block also carries two fields on the ordinary
    opt-in pattern (`showOnlyLastHeartbeat`, `rssTitle`) and an `else` branch of
    v1-only fields (`googleAnalyticsId`, `password`). This strengthens decision 5
    rather than undermining it: extending the rule to status pages would have
    collided with a server-side constraint that makes withholding impossible.
  - **Maintenance and settings carry no `2.0` gate at all.** `set_settings` gates
    at `1.23` and `1.23.1` only, and maintenance has no version gate. That does
    not establish that they have no v2-only surface — an *ungated* v2-only field
    is exactly the defect class of issue #12 and of this feature — so the
    follow-up must inventory them rather than conclude from the absence of a
    gate.
- **Issue #28, `SYSTEM_SERVICE` is under-gated on 2.0.x.** `system-service`
  first ships in 2.1.0, so on a 2.0.x server it passes the Type_Gate and creates
  a permanently-`PENDING` monitor, and the raised message names the wrong
  version. A monitor type is not a field, so this stays with #28. The coupling is
  recorded rather than resolved: #28 proposes a per-**type** version registry
  while decision 4 creates a per-**field** one, and requirement 4.8 requires the
  two to share a shape without merging.
- **Issue #29**, five `MonitorType` members missing against upstream plus
  `scripts/build_monitor_types.py` raising `KeyError` for any type absent from
  its hardcoded `titles` dict. Depends on #28.
- **A stale-pointer cleanup.** `v2-only-monitor-types-gate/design.md` under "Why
  the gate is 2.0 and not per-type", and the 2.3.1 CHANGELOG note on the same
  subject, both send the reader to #14 for the `SYSTEM_SERVICE` floor that #28
  now owns. Record-keeping, not a requirement of this feature.

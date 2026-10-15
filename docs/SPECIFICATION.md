# givlah behaviour specification

Status: **draft**, 15 October 2026. Defines the prototype's records, matching rules, plan lifecycle, privacy rules, failure handling and acceptance checks. Scope and screens: [PRODUCT](PRODUCT.md). Technical design: [ARCHITECTURE](ARCHITECTURE.md). No application code exists yet; every acceptance check below is **NOT RUN**.

## Inputs and records

| Record | Minimum fields / rules |
| --- | --- |
| User | Authenticated identity, display name, synthetic-demo flag. One person may fill compatible roles but acts/confirms only for themselves. |
| Locality | Named area/public neighbourhood zones; one explicitly selected scheduling batch. |
| Listing | Owner, title/description, 1-3 sanitized photos, condition, entered dimensions/handling needs, ownership/permission declaration, public zone, private pickup details, collection deadline, available windows, extra-helper requirement, server-owned synthetic-data provenance and revision. No price/payment. |
| Recipient offer | Listing, user, active/withdrawn state, windows, public destination zone and private destination details. Owner and recipient must differ. Interest is not allocation. |
| Transport offer | Specific listing, provider, mode (vehicle or carry locally), windows and declared item/trip suitability. Vehicle mode references one shared vehicle record, not a new alias per offer. Recipient may also be provider. |
| Helper offer | Listing, user, availability and active state. An extra helper must differ from owner, recipient and provider. MVP: zero or one extra helper. |
| Plan | Listing and selected offer versions; recipient/provider/helper; vehicle if used; reserved interval; revision, precise-detail approvals, confirmations, state and expiry. |
| Reservation | Plan, declared person/vehicle identity and occupied interval. Count each distinct person once; at most one active plan per listing. |
| Outcome/events | Separate owner and recipient handover records, versions, timestamps and transition reasons. No addresses copied into event text. |

Store UTC; display Asia/Kuala_Lumpur with date/time. Start must precede end; collection finishes by the owner deadline. Reserve the declared full interval including pickup, travel, unloading and contributor-declared return travel. Participants accept that interval; no route/travel estimate is inferred. This deliberately reserves the whole interval for each participant, rather than optimizing individual task timing.

## Candidate generation and matching

1. Read published, unexpired, unassigned listings and active offers in the selected batch. Existing pending/ready plans occupy resources and cannot be displaced.
2. Combine one owner, recipient and transport provider; include a vehicle when used and a distinct helper when required. Missing ownership consent, declared suitability, availability or a required role makes a combination ineligible.
3. Use exact common offered collection windows. Do not derive a shorter trip from partial availability overlap or infer travel-compatible times. The UI offers named date/time windows for explicit acceptance.
4. Check actual timestamp overlap using `[start, end)`. Different window IDs do not make overlapping reservations compatible. Adjacent windows are allowed only because the first interval already includes declared travel.
5. Enumerate at most eight listings / 24 feasible combinations. If the full set exceeds the cap, return an explicit limit response, not a truncated optimum. A deliberately smaller selected batch is allowed and labelled.
6. Maximize complete proposed handovers, one per listing, without overlapping any person/vehicle. Equal counts prefer earlier collection deadlines, then older listings, then stable IDs. No unproved social-priority score.
7. Return suggestions and source revision; suggestions reserve nothing. Owner selection is required. Explain missing roles, unsuitable transport, incompatible times and shared-resource contention. "Not selected in this set" is not "impossible".

The provider declares fit for this item; owner/recipient review it. Carry-local mode still needs an identified provider, not a vehicle. Likes never satisfy a role. Resource identity and suitability are self-declared, not externally verified.

Bounded-solve target: five seconds on the recorded development machine. Timeout/limit creates no commitment and labels the result incomplete. Never present a silent heuristic fallback as exact.

## Representative permitted demo path

Use fictional users O (owner), R (recipient), P (provider) and H (extra helper), clearly labelled synthetic zones and a test clock. Example item: an owned wooden shelf, declared 90 x 30 x 120 cm, with a sanitized permitted photo and a future two-hour window. Dimensions/fit are fixture declarations, not image deductions.

| Action | Expected observable output |
| --- | --- |
| O publishes; R wants it; H offers carrying help. | "Recipient interested; transport still needed"; no complete plan or reservation. |
| P offers declared suitable vehicle V for the full trip/window. | Complete suggestion O/R/P/H/V, not Ready. |
| O activates; O/R approve precise sharing; all four separately confirm. | Ready, one committed collection plan; public remains coarse, selected crew can review approved details. |
| P withdraws before collection starts. | Needs help, transport missing; every affected hold/access grant ends, unrelated collections remain. |
| New provider offers; owner activates a freshly checked version; everyone approves/confirms again. | Ready with new provider, no inherited confirmation. |
| After collection start, O records handover, then R records receipt. | Pending after O; Handover recorded only after R. Counts remain synthetic demo outcomes. |

G07 separately covers the competing-listing case. These are expected behaviors, not executed results.

## Plan activation, confirmations and states

Only the listing owner activates a suggestion. In a short write transaction, revalidate versions, eligibility, deadlines and current resource intervals. Acquire the listing and every required resource together or nothing. Create **Awaiting confirmations** with a hold ending at the earlier of **20 minutes after activation or collection start**. Pending holds are shown to affected participants; one active plan per listing prevents duplicate invitations.

Both owner and recipient explicitly approve sharing their respective precise details with this exact crew. Until both approve, the crew sees only public areas. Once approved, selected participants can review the trip. Final confirmation requires both approvals and acknowledgement of fit/handling and the full interval. Owner/recipient approvals and final confirmations are distinct actions. Any participant, time, address or material requirement change invalidates the plan version and needs fresh approvals/confirmations; no silent substitution.

| State | Meaning / entry | Exit and reservation rule |
| --- | --- | --- |
| Draft | Owner has not published valid required inputs. | Valid publish -> Needs help; no reservations. |
| Needs help | Available listing; partial offers or unactivated suggestions may exist. | Owner activates complete crew; otherwise cancel/expire as applicable. |
| Awaiting confirmations | Complete proposed crew held temporarily; show missing approvals/confirmations and expiry. | All distinct participants confirm current version -> Ready. Pre-start timeout/decline/material edit invalidates and releases every hold. |
| Ready | All current approvals/confirmations; committed reservations. | Pre-start withdrawal -> Needs help. At collection start -> Awaiting handover record; never auto-reallocate. |
| Awaiting handover record | Window started/ended or one party reported handover; completion unproved. | Both agree -> Handover recorded. Uncertain/conflicting/cancelled physical outcome -> Needs review. |
| Handover recorded | Selected owner and recipient separately agree it happened. | Remove from matching; retain historical occupied intervals/outcome. |
| Needs review | Late withdrawal or uncertainty whether the item moved. | Reopen only after both parties record that it stayed with the owner and is still available; otherwise keep out of matching. |
| Expired / Cancelled | Unassigned listing passed deadline or owner closed it. | No allocation. Preserve history and any unresolved physical-outcome record. |

Use server time on every read/mutation to reconcile holds and collection-window state; no worker required. An old page cannot keep a hold alive. Pre-start invalidation releases the entire affected plan, clears current confirmations and revokes precise access; unrelated plans stay intact. Replanning creates suggestions only.

After collection start, withdrawal revokes future precise access and requires outcome review. It never automatically relists the item. Keep recorded occupied intervals through their declared end, even if handover is reported early. Revocation cannot erase information already seen.

Only the selected owner/recipient may record handover after collection start on a plan that reached Ready. A never-confirmed plan cannot record completion. One record is pending, not completion. Identical repeats are idempotent. Retraction/disagreement removes completion and requires review; helpers cannot report for either party. A listing cannot expire out of a pending physical-outcome check. Reopening also requires valid new/current windows and deadline; old offers are revalidated, never automatically recommitted.

## Location and photo privacy

- Public responses/HTML/map data expose a named zone, not true coordinates. A future map uses its representative point. Hiding a precise point in the UI is insufficient; do not expose exact distances that reconstruct it.
- Store private pickup/destination separately from public fields. Precise access requires current plan membership, both location-owner approvals, the approved version and pending/ready/awaiting-outcome state. Replaced, expired, cancelled, review or completed plans grant no precise access. Even an unresolved active plan loses precise access seven days after collection end.
- Retain listing/offer private details while actively needed for planning; retention expires seven days after closure/deadline or the last associated collection end, whichever is later. Block access at expiry and purge on the next startup/request; an inactive local app has no scheduled deletion worker. Invalidating a plan immediately revokes its grant, without deleting an active owner's address needed for a new plan. Never copy addresses to plan/event history. Periodic purge/backup retention needs a decision before deployment.
- Unselected interested users and other logged-in users cannot fetch private fields by object ID. Enforce backend filtering/authorization, not just hidden buttons. Administrative edits follow the same state rules.
- Request GPS only on explicit action, once per attempt, ten-second timeout. Owner confirms/corrects it. Denied/inaccurate/unavailable GPS or an insecure phone origin permits manual named area/private-address input; never fake success or coordinates.
- Images: 1-3, at most 5 MiB/12 megapixels each; decoded JPEG/PNG/WebP only. Decode, apply camera orientation, resize to at most 1600 pixels on the longest edge, re-encode and strip metadata/GPS. Reject invalid/excess input and persist/serve only sanitized images, never originals or user-chosen paths.
- Owner reviews visible faces/addresses in photo/text before publication. Metadata stripping does not remove writing pictured in an image. No automated visual-redaction claim.
- No public phone/email, background location trail, analytics, external geocoder or live model in the critical path. Logs/errors/events omit precise location and image payloads.

Browser location needs permission and a secure context. Localhost behavior does not establish that HTTP on a phone's LAN origin works. [MDN geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API). HTTPS hosting is a separately authorized deployment choice, not a hidden local-build dependency.

## Commands and failure handling

Client: server-rendered Django PWA ([ARCHITECTURE](ARCHITECTURE.md)). These service commands are plain service functions called by views; they define actor, validation and recovery behavior independently of URL or transport, so a later API can reuse them:

| Command | Actor / validation | Failure / recovery |
| --- | --- | --- |
| Publish/edit/close listing | Owner; valid input, revision, permission declaration. | Field errors preserve other form fields. Material edits invalidate affected plans atomically. Forged ownership/status rejects. |
| Add/edit/withdraw offer | Offer owner; valid listing/role/window/fit. | Closed/expired target rejects; material change follows withdrawal/replanning rules. |
| Suggest plans | Authenticated user; selected local batch. | Explain missing roles, contention, limits or timeout; no commitments. |
| Activate plan | Listing owner; source revision/current eligibility/resources. | Stale/conflict -> 409 and current explanation; zero partial reservation. |
| Approve/revoke precise sharing / confirm / decline | Current participant and exact plan revision; approval/revocation belongs to location owner. | Unauthorized -> 403/non-disclosing 404; expired/stale -> 409 and current state. Revocation invalidates affected plan. Posted actor IDs never establish identity. |
| Record/retract outcome | Selected owner/recipient; started collection window. | Repeat harmless; conflict requires review, not forced completion. |
| Read status/private details | Permission-filtered server representation. | Omit unauthorized private fields entirely; fetch truth after mutation/reload. |

Mutations require authentication and CSRF; no GET mutation. Separate synthetic accounts enable real-session checks. Any demo account switch is explicitly labelled and disabled outside demo mode. No credentials in source and no external notification/account provider required.

Disable duplicate buttons while pending; also enforce unique action tokens/object versions server-side. Lost-response retry returns the committed result; genuinely stale input returns current state. Database/server failure must show "not confirmed; refresh to check", not false success. Preserve entered non-sensitive fields and offer bounded manual retry.

## Persistence and concurrent writes

Planning baseline: Django/SQLite for a small local prototype. Use explicit short atomic transactions with SQLite `transaction_mode=IMMEDIATE`; no indiscriminate transaction-per-page. SQLite `select_for_update()` does not lock rows. [SQLite behavior](https://docs.djangoproject.com/en/5.2/ref/databases/#transactions-behavior), [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

Compute suggestions outside the transaction. Within every activation/confirmation/withdrawal/outcome write, reload versions, reconcile expired holds, check interval overlap and commit state/reservations/events together. Database constraints enforce one active plan per listing, unique action/confirmation records and references. Serialized writes plus repeated overlap validation protect intervals; every writer, including admin changes, uses these services.

Database busy wait: five seconds, then retryable contention; no infinite retry. No network, solver search or image decoding inside reservation transactions. Rollback leaves no partial reservation, confirmation, outcome or success event. Persist across refresh/restart. Fixture reset is explicit/local and forbidden against non-demo data. Public multi-user deployment/scaling is not verified by local SQLite checks.

## Observable acceptance checks

Status: all **NOT RUN**; no application code exists yet. Execute each check on an identified commit and record the command or interaction, date, result and counts. Exercise actual services, database and separate sessions. Clearly label simulated browser boundaries; ordinary tests make no paid or external-network calls.

| ID | Scenario and independently expected result |
| --- | --- |
| G01 | Post valid sanitized photo with requested GPS; publish location only after confirmation. Denied/timed-out GPS permits truthful manual post. Inspect real rendered camera/gallery behavior in a supported browser. |
| G02 | Other user cannot edit listing, alter someone else's offer, impersonate a confirmer or fetch private details/original media. Missing authentication/CSRF rejects mutation. |
| G03 | Invalid/disguised/oversized images reject. GPS-tagged accepted image re-encodes without metadata/GPS and respects dimensions. Public HTML/responses contain no structured private point/address fields; photographed/text-entered identifying details still require owner review. |
| G04 | Missing role/ownership/fit, incompatible time or expired listing never yields an eligible complete plan; reasons distinguishable. |
| G05 | Recipient also transports: reserve person/vehicle once. Carry-local mode needs no vehicle; extra helper cannot be an already-counted person. |
| G06 | Overlapping intervals with different IDs cannot share person/vehicle. Adjacent windows are allowed with all declared travel already included. |
| G07 | Independent synthetic witness: same interval, A needs P+X, B P+Y, C Q+X; all other users distinct. Exact suggestions B+C -> two; stable A-first scarcity greedy -> one; exhaustive reference -> two. No actual impact/time-saving inference. |
| G08 | Generated small inputs agree with independent exhaustive feasible-subset enumeration, including combined roles, existing reservations, time overlap and withdrawals; report ties. |
| G09 | Eight listings/24 combinations solve within five seconds on recorded machine. Over-limit/forced-timeout paths claim no truncated optimum and create no commitments. |
| G10 | Two real DB connections activate conflicting plans concurrently: at most one succeeds; loser has zero partial writes. Disjoint plans can both succeed. |
| G11 | Inject failure after partial reservation writes: whole transaction rolls back. Lost-response duplicate activation/confirmation creates only one plan/record. |
| G12 | Separate sessions approve precise sharing and finally confirm. Any missing approval/confirmation stays pending; only all current distinct confirmations make Ready. Unselected users get no private fields. |
| G13 | Expire hold or reach collection start before final confirmation: old plan cannot become Ready; holds/access end. Use injected server time, not wall-clock sleeps. |
| G14 | Pre-start withdrawal/edit/revocation invalidates affected plans, releases all holds, clears old confirmations and revokes precise access. Unrelated plans remain. Old versions reject; replacements approve/confirm anew. |
| G15 | New posts/replanning preserve Ready plans. Owner choosing another feasible set cannot retain the old optimal-count claim. |
| G16 | Late withdrawal or partial handover never auto-relists; uncertain outcome needs review. Reopen only after both parties record that item stayed with owner. |
| G17 | One handover record stays pending; two agreeing records complete once. Outsider/helper/too-early/never-ready records reject; conflicting/retracted records remove completion. Early reporting does not shorten occupied interval. |
| G18 | Reload/restart retains truth; expiry derives from server time without worker. Invalidated/completed plans and access past seven days return no precise location; closed private-data purge meets retention. |
| G19 | Render full flow at phone/desktop sizes: keyboard usable, errors readable, roles/expiry visible, state not colour-only, request failure never shows success. This is not a user study. |
| G20 | Totals count unique dual-recorded listings; incomplete/retracted and demo outcomes are separate. Critical path runs without providers/external network; document actual dependencies, MIT notices and material AI use. |

Prototype completion requires the core path and relevant failure checks after final code changes. Document reviews do not satisfy G01-G20. Physical collection, adoption and environmental benefit remain separate evaluation work.

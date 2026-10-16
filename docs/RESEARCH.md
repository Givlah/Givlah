# Research, gap and alternatives

Givlah explores a specific question: **can neighbours turn separate offers of an item, transport and carrying help into a complete collection plan?** This summary explains the public evidence behind that question, relevant alternatives and the limits of the prototype.

Public sources checked on **16 October 2026**. This is desk research and a description of the implemented prototype, not a resident study or a hands-on competitor evaluation. Linked product pages describe their providers' own policies or advertised capabilities. Availability, coverage and full configurations were not tested; an undocumented feature remains unknown.

## The problem supported by the sources

Paul Chad's 2023 study, *Rescuing Unwanted Household Goods: Moving Towards a Circular Economy*, examines household behaviour and the perspectives of local-government employees and collection contractors. It identifies coordination and practical enablement among the issues involved in extending the life of unwanted goods. It supports investigating barriers beyond awareness; it does not establish demand for Givlah or the frequency of failed collections in Malaysian townships. [Published study and abstract](https://journals.sagepub.com/doi/abs/10.1177/14413582231165268).

Existing services also recognise collection needs. Olio allows a friend, neighbour or family member to collect on someone's behalf, while its free-sharing policy prohibits asking for or offering delivery/postage. In Malaysia, The Salvation Army provides a bulky-item donation collection channel accepting item descriptions, photographs and location details. These are existing ways to get help, rather than evidence that collection is universally unsolved. [Olio policy](https://help.olioapp.com/en/articles/12238795-can-i-ask-or-offer-to-deliver-on-olio), [The Salvation Army Malaysia](https://www.salvationarmy.org.my/contact-us/).

**Our design inference:** finding an interested recipient can still leave people, suitable transport and a shared collection window to arrange. Givlah makes those requirements explicit. The sources motivate this hypothesis; they do not prove that another app is needed.

## Competitors and other alternatives

These examples cover item sharing, paid help, organised donation logistics and general scheduling. They are not an exhaustive market survey or a ranking.

| Alternative | What its public source establishes | How it informs Givlah's scope |
| --- | --- | --- |
| [Olio](https://help.olioapp.com/en/articles/12238795-can-i-ask-or-offer-to-deliver-on-olio) | Local free sharing, with collection by a friend or neighbour permitted; delivery/postage requests and offers are prohibited for free items. | Acknowledges an existing collection workaround. Givlah explicitly represents recipient, transport and helper commitments. |
| [Tiptapp](https://help.tiptapp.com/en/articles/12858266-how-do-i-post-an-ad-in-tiptapp) | Users post a task, photo, address, preferred time and price, then select a helper. Categories include moving, delivery and giving away. | Paid collection help is an existing alternative. Givlah's prototype uses resident-offered contributions without payments. |
| [The Salvation Army Malaysia](https://www.salvationarmy.org.my/contact-us/) | A collection enquiry/booking channel for bulky donated goods, including furniture. | Donation collection already exists locally. Givlah explores direct neighbour-to-neighbour arrangements; it has no collection fleet or service guarantee. |
| [Furnish Forward](https://furnish-forward.com/) | Advertises furniture listings, recipient claims and volunteer moving-company assignment for consolidated pickups in the Bay Area. | Closely related logistics prior art. Givlah assembles declared resident offers without an established moving-company network. The advertised service and its outcomes were not independently verified. |
| [Nearby](https://nearbyapp.social/) | Advertises paid/free neighbourhood tasks and teams of two to four helpers for moving or heavy lifting. | Multi-person help is already an advertised capability. Givlah focuses on item-specific roles, shared-resource conflicts across listings and plan confirmation. The advertised workflow was not exercised. |
| [SignUpGenius](https://support.signupgenius.com/hc/en-us/articles/29435544326679-Create-a-Sign-Up) | Supports dates, time slots, participant roles and capacity limits. | Structured role/time signup is established. Givlah connects contributions to item eligibility, person/vehicle reservations and handover records. |
| A neighbourhood group and spreadsheet | A manual baseline, not a tested product claim. People can record requirements, compare combinations and agree a collection. | A carefully maintained spreadsheet can implement the same exhaustive matching. Givlah packages those rules into a workflow; lower effort and better outcomes have not been measured. |

This comparison does **not** establish that alternatives lack cross-listing matching, confirmations or recovery in every configuration. No worldwide-first, unique-algorithm or general superiority claim follows.

## The gap Givlah targets

Givlah combines these behaviours in one bounded local prototype:

1. Assemble a complete recipient, transport provider and extra carrying helper where required, using declared availability and suitability.
2. Compare complete combinations across listings while preserving existing holds and confirmed plans. Avoid overlapping reservations for the same declared person or vehicle.
3. Hold an invited crew briefly, obtain private-location approvals and require every distinct participant to confirm the same plan version.
4. Recover from expiry or withdrawal. Once collection may have started, require outcome review before reopening the item.
5. Count a handover only after separate owner and recipient records, keeping synthetic outcomes separate.

Matching is bounded to eight open listings and 24 feasible combinations per batch. It does not optimise routes, certify safe handling or supply missing volunteers. See the [matching and workflow contract](SPECIFICATION.md#candidate-generation-and-matching), [implementation](../apps/coordination/) and [architecture](ARCHITECTURE.md).

### Why compare across items?

Consider three items in the same time interval. A needs person P and vehicle X; B needs P and vehicle Y; C needs person Q and vehicle X. All other participants are distinct. Choosing A blocks B and C. Choosing B and C permits two complete arrangements.

This constructed example explains why independently choosing the first feasible crew can miss another feasible set. Exhaustive manual comparison can reach the same result. It says nothing about how frequently these conflicts occur, how much time Givlah saves or how many real collections it enables.

## What the evidence can and cannot show

The [demo and dated software checks](https://givlah.vercel.app/#verification) show local application behaviour with synthetic people, items, locations and outcomes. The repository includes [matcher comparisons](../apps/coordination/test_matcher.py) and [workflow tests](../apps/coordination/tests.py). These are software checks, not independent validation of the product's usefulness or competitors' service quality.

No resident interviews, real physical collections, comparative user study or environmental-impact measurement are reported here. Demand, transport participation, trust, moderation effort and operating costs remain open questions. A meaningful field comparison would observe a consenting community's existing coordination, eligible listings, failed arrangements, coordination effort and separately confirmed handovers over a stated period. Avoided disposal would need additional evidence; neither a match nor two recorded confirmations establishes it.

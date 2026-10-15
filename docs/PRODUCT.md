# Givlah product overview

**Help neighbours give usable household items a new home by arranging the people, transport and time needed to collect them.**

## Users and outcome

The first users are residents of a single Malaysian township:

- **Owner:** has an owned, usable item they no longer need.
- **Recipient:** wants the item. They may be able to transport it themselves.
- **Transport provider:** a neighbour with a vehicle, or someone who can carry the item locally.
- **Helper:** an extra neighbour who can help carry, when the item needs it.

Finding a recipient is not enough to get an item moved. The intended outcome is an agreed collection, followed by a handover that both the owner and the recipient record.

Givlah does not guarantee participation, truthful declarations, physical safety or that items are kept out of landfill. Early scenarios use clearly labelled synthetic data.

## Workflow

1. **Offer an item.** Photograph it and declare that you own it or are allowed to give it away. Add condition, dimensions, handling needs, a collection deadline and the times you're available. GPS can suggest the pickup location when you ask, and you confirm or correct it.
2. **Share locally.** The public card shows the photo, the neighbourhood area, the deadline and a status such as "recipient interested; transport needed".
3. **Neighbours contribute.** Three actions: "I'd like this", "I can transport it" and "I can help carry". Each offer states availability. Transport offers also state the mode, the vehicle if one is used, and a declaration that the item fits.
4. **Suggest arrangements.** Givlah combines stored offers into complete crews and times across the open listings, without booking any person or vehicle twice. It explains what is missing or conflicting.
5. **Confirm.** The owner activates a suggestion, which holds it briefly. The owner and recipient approve sharing their exact details with this crew, and every participant confirms the same plan version.
6. **Collect and record.** After the collection starts, the owner and the recipient each record the handover. One record alone is not completion.
7. **Recover.** If someone withdraws or a hold expires before the collection starts, the listing returns to "needs help" with the missing role shown. Once a collection may have started, the item cannot be relisted until both parties confirm it is still with the owner.

## Defining capability

**Turn separate recipient, carrier and helper offers into complete collection arrangements across competing listings, without double-booking anyone's declared time or vehicle.**

- Explain unmet requirements and shared-resource conflicts. Likes never fill a missing role.
- Recipients may provide their own transport, and are then counted once. Items carried locally need no vehicle.
- Rely on declared suitability and availability. People confirm item fit and the full trip. A photo establishes neither.
- Hold a proposed crew briefly, then require every distinct participant to confirm the same plan version.
- Keep confirmed arrangements intact when new listings arrive. Never silently replace a person, time or item.
- Recover from withdrawals and expired invitations, and require an outcome check before relisting once a collection may have started.
- Show completion only after separate owner and recipient handover records.

## Items

Owner-authorised, reusable furniture and simple non-electrical household items. The following are excluded:

- electrical goods
- mattresses
- hazardous waste
- roadside items taken without the owner's consent

Suitability declarations are self-reported prerequisites, not professional certification.

## Prototype scope

| Priority | Scope |
| --- | --- |
| Core: inputs | Installable mobile web app with photo and location as first-class actions; separate user accounts; listings with sanitized photos; GPS on request with manual fallback; public area; condition, size, deadline, availability and carrying needs. |
| Core: contributions | Recipient interest, item-specific transport offers and an optional extra helper, each with explicit availability, transport mode, vehicle identity where used and suitability declarations. |
| Core: coordination | Suggestions generated from stored offers across listings; explanations of missing roles and conflicts; owner activation; expiring holds; approvals for sharing exact locations; confirmation by every participant; withdrawal and replanning; handover records from both parties. |
| Core: reliability | Object-level permissions, protection of private locations, sanitized images, persistence, handling of stale and repeated requests, clear failure messages and labelled synthetic data. |
| Later, if useful | Map browsing, richer search and filtering, in-app comments, expanded activity history. |
| Not in the prototype | Payments or paid hauling; route optimisation or multi-stop packing; judging safety or weight from photos; AI assistant; rankings or likes; email, SMS and push notifications; commercial launch. |

The first version plans one locality. Each scheduling batch is explicitly selected, with at most **eight open listings and 24 feasible candidate combinations**, and a larger set is reported as over the limit rather than silently cut down.

## Screens

| Screen | Main action and information |
| --- | --- |
| Nearby | Item photo, public area, deadline and useful status. Synthetic data is labelled. |
| Offer an item | Photo, ownership/permission declaration, condition, dimensions, location confirmation, deadline, time windows and required help. Valid fields are kept when another field has an error. |
| Item detail | Requirements and the three contribution actions. Offers can be edited, and one person can combine roles where that's allowed. |
| Collection review | Crew and roles, the full reserved time, declared fit, approvals for sharing private details, remaining confirmations and when the hold expires. The owner activates; each participant acts only for themselves. |
| My activity | Listings, offers, invitations, withdrawals and handover actions, always reloaded from the server. |

Solver and dependency jargon stays out of resident-facing screens, and so do invented environmental totals.

## Visual direction

The app icon (`assets/brand/givlah-icon.svg`) shows a parcel between green and blue waves. The UI uses its palette:

| Role | Colours |
| --- | --- |
| Green (primary) | `#34E180` to `#10C766` |
| Blue | `#278FFF` to `#1785FC` |
| Gold / orange accent | `#FFDA7B`, `#FFBD30` to `#F3A027` |
| Surfaces | near-white `#FDFCFD`, cream `#FFF7E9` |

Interaction principles:

- Make the primary task obvious and optimise the common paths.
- Offer few competing choices, and reveal detail progressively.
- Keep spacing and components consistent.
- Give immediate feedback.
- Keep navigation predictable and preserve the user's context.
- Use motion only when it explains a change of state.

Keep text contrast readable, and never use colour as the only signal of status.

## Measuring outcomes honestly

The primary measure is the number of unique listings with both handover records. It is reported for a stated observation period, out of the published listings that were eligible.

Proposed, ready, incomplete, cancelled and unconfirmed outcomes are counted separately. Synthetic demo outcomes never count toward real totals. Givlah does not automatically estimate kilograms, CO2 or avoided landfill.

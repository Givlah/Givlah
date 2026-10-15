<p align="center">
  <img src="assets/brand/givlah-icon.png" alt="givlah icon: a parcel between green and blue waves" width="120">
</p>

# givlah

**Good things. New homes. Together.**

givlah helps neighbours give usable household items a new home. It does more than find someone who wants an item. It arranges the people, transport and time needed to actually collect it.

> **Status: early development.** This repository currently holds the product, behaviour and architecture documents plus brand assets. The application code has not been written yet, so there is nothing to install or run.

## The problem

Someone has a usable bookshelf they no longer need, and a neighbour wants it. But the neighbour has no car, and the shelf needs two people to carry. Giveaway groups help people find each other, but that is where they stop. The item often ends up waiting or thrown away because nobody can organise the collection.

## How givlah works

```mermaid
flowchart LR
    A[Photograph an owned, usable item] --> B[Confirm location and collection needs]
    B --> C[Share with the neighbourhood]
    C --> D[Neighbours offer to take it, transport it or help carry]
    D --> E[givlah suggests a complete crew and time]
    E --> F["Owner and recipient approve sharing exact addresses, everyone confirms"]
    F --> G[Collect, then owner and recipient both record the handover]
    F --> H[Someone withdraws or a hold expires: show what help is missing]
    H --> D
```

What makes givlah different:

- **Complete arrangements, not likes.** A collection is ready only when it has a recipient, someone to transport the item (or carry it locally) and an extra helper if one is needed. All of them must be free for the whole trip.
- **No double-booking.** givlah plans across several listings at once. It never books the same person or vehicle into overlapping trips, and it explains why a listing can't be planned yet.
- **Everyone confirms for themselves.** A proposed crew is held briefly. It becomes Ready only after every participant confirms the same version of the plan. Any change requires fresh confirmations.
- **Honest recovery.** If someone withdraws, the plan returns to "needs help" with the missing role shown. Once a collection may have started, the item is never automatically relisted.
- **Handover takes two records.** A collection counts as complete only after the owner and the recipient each record the handover separately.

## Privacy by design

- Public listings show only a neighbourhood area, never an exact location.
- Exact pickup and drop-off details are visible only to the selected crew. Both the owner and the recipient must approve sharing them, and access ends when the plan changes or closes.
- Location is requested only when you tap the button for it, and you can always enter it by hand.
- Photos are re-encoded with location and camera metadata removed. Originals are never stored.
- No phone numbers or emails are shown publicly. There are no analytics or third-party trackers.

## Architecture at a glance

givlah is planned as an **installable mobile web app (PWA)** served by **Django**:

- Server-rendered Django 5.2 templates, designed for phones first.
- Camera capture through the browser's file input, and location through the Geolocation API.
- Coordination rules (matching, holds, confirmations and handovers) implemented as plain Python service functions, kept separate from the views.
- SQLite with short serialized write transactions for the local prototype.
- No paid services, external APIs or background workers on the critical path.

Full details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Users, workflow, prototype scope, screens and visual direction |
| [docs/SPECIFICATION.md](docs/SPECIFICATION.md) | Records, matching rules, plan states, privacy rules, failure handling and acceptance checks |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Client choice, components, data model, transactions, PWA behaviour and testing approach |

## Repository layout

```
assets/brand/   App icon (SVG source and 2048 x 2048 PNG)
docs/           Product, specification and architecture documents
```

The planned application layout is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#project-layout).

## Getting started

Not available yet. Setup and run instructions will be added here once the first runnable version exists.

## Use of AI tools

The planning, specification and architecture documents in this repository were drafted with AI assistants, including Claude by Anthropic, and reviewed and directed by the maintainer. This section will record any AI assistance with application code as that work happens. The app itself does not use an AI model.

## License

No license has been chosen yet. Until one is added, all rights are reserved.

# Givlah documentation site

Buildless HTML, CSS and JavaScript. No added dependencies, API, analytics or server functions. All shipped assets are local. Django behaviour is unchanged.

## Preview

From the repository root:

```sh
python -m http.server 8011 --bind 127.0.0.1 --directory site
```

Open http://localhost:8011. This is the guide, not the Django app. The app setup is in the guide and the repository README.

## Hosting configuration (prepared, not deployed)

Vercel project settings: Root Directory `site/`, Framework Preset **Other**, no install/build command, Output Directory `.`. No functions. Keep the Vercel Toolbar and analytics disabled so the guide has no injected third-party scripts. `vercel.json` includes response headers and an Ignored Build Step. The step compares the previous deployment commit (or previous commit when unavailable), builds if history is missing, and skips commits with no changes in `site/`. See the [Vercel ignored-build documentation](https://vercel.com/kb/guide/how-do-i-use-the-ignored-build-step-field-on-vercel).

The Django app needs a separate host, persistent database and sanitized-media storage; it does not run on Vercel. On that future host, watch app paths and ignore site-only commits. A provider-neutral Git change check, run from the repository root, is:

```sh
git diff --quiet "$PREVIOUS_DEPLOY_SHA" HEAD -- . ':!site/**'
```

Exit 0 means no app change; exit 1 means app changes exist. Map those results to the future host's build/skip convention. When the base is missing, build. No app deployment provider or hook is configured by this task.

## Pending external links

- Video: set the real eleven-character YouTube ID in `index.html`'s `data-video-id`. The local poster and written chapter summary remain available. Add actual timestamps/captions only after checking the recording. Confirm that its public title, description, tags and thumbnail describe Givlah consistently. The embed contacts `youtube-nocookie.com` only after Play. A plain Watch on YouTube link appears when the ID is configured. No-JavaScript visitors retain the written guide.
- Hosted app: replace the explicit pending message with the verified demo URL and actual reset schedule. Keep the synthetic-only and possible cold-start notices. Do not describe a deployment as available before checking it.

## Content and assets

Behaviour sources: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/SPECIFICATION.md`, README and implementation. The specification's draft execution-status text predates implementation; the site's dated executed checks are a separate report. App state used for captures and checks: `d1c75a5` on 16 October 2026. Windows clean-setup commands were executed; the equivalent macOS/Linux commands were inspected but not executed on those platforms.

`assets/demo/` contains real Edge captures of the local app, driven through forms with separate synthetic-user sessions. A controlled server clock advances to collection start for the handover branch. All captured people, addresses, items and outcomes are fictional. `review.png` shows a separate retraction branch after the successful handover; `outcomes.png` is captured before the retraction. These captures do not establish real-world use.

Fonts are copied from the app's self-hosted Givlah Bold and Caveat assets; their notices are in `assets/fonts/`. The icon is the existing brand SVG. AI-use disclosure follows the root README: AI coding assistance, AI-generated in-app illustrations and fictional demo item photos.

For checks, serve the directory, inspect internal anchors and local asset responses, render at phone/desktop widths, test the keyboard and no-JavaScript path, print layout, reduced motion and colour contrast. Exercise the configured video branch with external network replaced at its iframe boundary; that verifies local behaviour, not a live recording. Real-device camera/GPS, HTTPS installation, screen-reader use, multi-user hosting and real resident use remain unverified.

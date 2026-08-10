# Furina Lab

Separate web dashboard for the Furina Engineering Company. It is intentionally not imported by the Furina APK/web application.

## Deployment
Create a separate Vercel project from the `WynnDev-rill/furina` repository and set the project Root Directory to `furina-lab`.

Required environment variable:
- `GITHUB_TOKEN`: fine-grained GitHub token with read access to the private Furina repository (Contents, Issues, Pull Requests, Actions read are sufficient for the dashboard).

Optional:
- `FURINA_REPO` (default `WynnDev-rill/furina`)
- `FURINA_STATE_ISSUE` (default `42`)

The token stays server-side in `api/status.js`; it is never sent to the browser.

## Worker state
The dashboard reads machine state from GitHub issue #42 and live GitHub PR/commit/workflow data. The browser polls the Vercel API every 20 seconds, so agent status changes do not require a dashboard redeploy.

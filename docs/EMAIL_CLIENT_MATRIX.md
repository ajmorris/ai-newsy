# Email client matrix

Checked by rendering `emails/render_email.mjs` and reading the HTML. There is no Litmus or Email on Acid run in CI. Confirm a real send in these clients before calling the theme done.

## Local preview

`./scripts/preview_email.sh` writes `emails/preview/index.html` and, when Mailpit is running, injects the same message at `http://localhost:8025`.

```bash
docker compose -f emails/docker-compose.mailpit.yml up -d
./scripts/preview_email.sh
```

The default sample is `execution/fixtures/email_preview_payload.json`. It is one email with eight stories, the renderer cap, plus every quick-hit section. Open the HTML file in a browser. Mailpit adds an inbox view with desktop and mobile widths, a light/dark toggle (`prefers-color-scheme`, which is what Apple Mail uses), and an HTML check that flags CSS Gmail and Outlook strip. Mailpit does not screenshot Outlook desktop's Word engine or Gmail's preprocessor. Start Mailpit with the Compose file above, or with the binary from the [Mailpit install docs](https://mailpit.axllent.org/docs/install/). The HTML file is still written when Mailpit is down.

`./scripts/preview_email.sh --date 2026-10-30` renders that digest with the send-path payload builder, so a section that the issue does not have is absent. `./scripts/preview_email.sh --payload path/to/renderer-payload.json` skips the builder.

The default sample includes:

- "Covered by N sources", with "Also covered by" links and "Where coverage differs"
- "Update · Covered by N sources"
- a cluster line that is only "Update"
- a multi-source line with no extra source names and no conflict text
- a story with no cluster, and a cluster the renderer hides (`badge_count` under 2 and not an update)
- an image on some stories and no image on others
- a read time on some stories and none on others, in the TL;DR and on the story
- empty summary and empty why, which render "No summary available." and "Follow the source for details."
- Twitter/X items with a linked phrase, a "Source" link, no URL, a summary, and "Covered by N sources"
- a community summary, "What this means for people leading change", and a covered-by line
- "Developer and open source" with a covered-by line
- "The human side" with two items, one of them a meaning line

## Clients

| Client | Expectation |
| --- | --- |
| Apple Mail (iOS, macOS) | Custom dark theme from `prefers-color-scheme` |
| Gmail web | Light theme, the inline default |
| Gmail iOS / Android | Light theme, still readable if the client inverts |
| Outlook.com / Outlook mobile | Dark overrides via `[data-ogsc]` and `[data-ogsb]` |
| Outlook desktop (Windows) | No media query; off-white and near-black survive inversion |
| Yahoo / AOL | Light default; off-white and near-black if inverted |

Neither theme uses `#ffffff` or `#000000` for text or page background. Text and accent pairs in `emails/tokens.json` must stay at or above 4.5:1.

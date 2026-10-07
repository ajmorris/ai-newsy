# Email client matrix

Checked by rendering `emails/render_email.mjs` and reading the HTML. There is no Litmus or Email on Acid run in CI. Confirm a real send in these clients before calling the theme done.

| Client | Expectation |
| --- | --- |
| Apple Mail (iOS, macOS) | Custom dark theme from `prefers-color-scheme` |
| Gmail web | Light theme, the inline default |
| Gmail iOS / Android | Light theme, still readable if the client inverts |
| Outlook.com / Outlook mobile | Dark overrides via `[data-ogsc]` and `[data-ogsb]` |
| Outlook desktop (Windows) | No media query; off-white and near-black survive inversion |
| Yahoo / AOL | Light default; off-white and near-black if inverted |

Neither theme uses `#ffffff` or `#000000` for text or page background. Text and accent pairs in `emails/tokens.json` must stay at or above 4.5:1.

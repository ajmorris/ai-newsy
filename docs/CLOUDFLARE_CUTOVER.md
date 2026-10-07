# Cloudflare cutover checklist

This change adds a Worker, a D1 schema, and an R2 bucket beside the live stack. It does not change DNS. Vercel still serves the site, Supabase still stores subscribers and articles, Resend still sends the daily digest from GitHub Actions, and generation still runs in `.github/workflows/digest_pipeline.yml`.

Do not change DNS in the pull request that adds this app. Do not point the domain at the Worker, and do not delete the Vercel project, the Supabase project, or the Resend domain.

## What is already in place

- `workers/digest` is a Worker. `POST /api/publish` stores an issue when `Authorization: Bearer $PUBLISH_TOKEN` matches. Finalize calls it only when `CLOUDFLARE_PUBLISH_URL` and `CLOUDFLARE_PUBLISH_TOKEN` are set. Until then the step is skipped.
- Issue objects in R2 use `data/digests/YYYY-MM-DD.json`. Archive HTML, when the publish body includes it, is stored at `issues/YYYY-MM-DD.html`, the same path the static site uses today.
- D1 migrations live in `workers/digest/migrations`. Integer primary keys replace `BIGSERIAL`. JSON columns are text. Timestamps are ISO-8601 strings. There is no row level security and no stored procedure. The Worker checks the publish token and the unsubscribe signature itself.
- `sendEmail()` defaults to Resend. `EMAIL_ADAPTER=cloudflare` is implemented and refuses to send until Email Sending is generally available.
- The send cron is deployed with `SEND_CRON_ENABLED=0`, so a deploy cannot double-send while GitHub Actions still owns delivery.
- Idempotency key is `issue_id+subscriber_id`.
- Subscribe is double opt-in. Messages that go out through `sendEmail()` include `List-Unsubscribe` and `List-Unsubscribe-Post`. Unsubscribe tokens are HMAC-signed. A bounce posted to `/api/webhooks/bounce` sets `suppressed_at`, and the cron skips that address.

## DNS and authentication records, documented only

Add these on the sending domain when you are ready to warm up. Leave DMARC at `p=none`. Do not change that policy in the same step as the first Worker send.

- SPF: include the Resend servers you already use. Add the Cloudflare Email Sending include only after that product is generally available and you have switched `EMAIL_ADAPTER`.
- DKIM: keep the current Resend selectors. Add a Cloudflare selector later, beside them.
- DMARC: `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain`. Stay on `p=none` through the warm-up and the two-week rollback window.

## Warm-up

1. Deploy the Worker and apply the D1 migration to a staging database. Do not change DNS.
2. Set `CLOUDFLARE_PUBLISH_URL` and `CLOUDFLARE_PUBLISH_TOKEN` on the finalize job so new issues are copied. The git JSON file remains the canonical issue.
3. Turn `SEND_CRON_ENABLED` on for a staging audience only. Keep `EMAIL_ADAPTER=resend`.
4. Send to a small confirmed segment first. Watch bounces and set `suppressed_at` from the bounce webhook.
5. Compare a week of Worker sends with the GitHub Actions send before moving the rest of the list.

## Two-week rollback

After the first production send from the Worker, keep Vercel, Supabase, and Resend live for two weeks.

- To roll back, set `SEND_CRON_ENABLED=0` and leave the GitHub Actions send job as it is.
- Do not delete subscriber rows from Supabase during those two weeks. D1 is a second copy, not a replacement, until the window closes.
- Issue URLs stay `/issues/YYYY-MM-DD.html`.

## Seven-send shutdown

After seven successful production sends from the Worker, with no rollback, you can retire the GitHub Actions send:

1. Disable the send job in `digest_pipeline.yml`.
2. Keep finalize writing `data/digests/YYYY-MM-DD.json` and publishing that file to the Worker.
3. Leave the Vercel project in place until the archive has been read from R2 for a full week.
4. Export Supabase and only then plan to turn that project off. That shutdown is a later change, not this one.

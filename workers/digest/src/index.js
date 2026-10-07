import { idempotencyKey, listUnsubscribeHeaders, sendEmail } from "./send-email.js";
import { signUnsubscribe, verifyUnsubscribe } from "./tokens.js";

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function authorized(request, env) {
  const header = request.headers.get("Authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
  return Boolean(env.PUBLISH_TOKEN) && token === env.PUBLISH_TOKEN;
}

function issueObjectKey(digestDate) {
  return `data/digests/${digestDate}.json`;
}

function archiveHtmlKey(digestDate) {
  return `issues/${digestDate}.html`;
}

export async function publishIssue(request, env) {
  if (!authorized(request, env)) {
    return json({ error: "unauthorized" }, 401);
  }
  const payload = await request.json();
  const issueId = String(payload.issue_id || "").trim();
  const digestDate = String(payload.digest_date || "").trim();
  if (!issueId || !digestDate) {
    return json({ error: "issue_id and digest_date are required" }, 400);
  }
  const publishedAt = new Date().toISOString();
  const body = JSON.stringify(payload);
  await env.DB.prepare(
    `INSERT INTO issues (issue_id, digest_date, payload, published_at)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(issue_id) DO UPDATE SET
       digest_date = excluded.digest_date,
       payload = excluded.payload,
       published_at = excluded.published_at`
  )
    .bind(issueId, digestDate, body, publishedAt)
    .run();
  if (env.ISSUE_ARCHIVE) {
    await env.ISSUE_ARCHIVE.put(issueObjectKey(digestDate), body, {
      httpMetadata: { contentType: "application/json; charset=utf-8" },
    });
    if (typeof payload.archive_html === "string" && payload.archive_html) {
      await env.ISSUE_ARCHIVE.put(archiveHtmlKey(digestDate), payload.archive_html, {
        httpMetadata: { contentType: "text/html; charset=utf-8" },
      });
    }
  }
  return json({ ok: true, issue_id: issueId, digest_date: digestDate });
}

export async function readIssueArchive(request, env) {
  const url = new URL(request.url);
  const match = url.pathname.match(/^\/issues\/(\d{4}-\d{2}-\d{2})\.html$/);
  if (!match || !env.ISSUE_ARCHIVE) {
    return new Response("Not found", { status: 404 });
  }
  const object = await env.ISSUE_ARCHIVE.get(archiveHtmlKey(match[1]));
  if (!object) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(object.body, {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

async function subscribe(request, env) {
  const payload = await request.json().catch(() => ({}));
  const email = String(payload.email || "").trim().toLowerCase();
  if (!email.includes("@")) {
    return json({ error: "email is required" }, 400);
  }
  const confirmToken = crypto.randomUUID();
  const subscribedAt = new Date().toISOString();
  try {
    await env.DB.prepare(
      `INSERT INTO subscribers (email, confirm_token, confirmed, subscribed_at)
       VALUES (?, ?, 0, ?)`
    )
      .bind(email, confirmToken, subscribedAt)
      .run();
  } catch (error) {
    return json({ error: "already subscribed" }, 409);
  }
  const confirmUrl = new URL("/api/confirm", request.url);
  confirmUrl.searchParams.set("token", confirmToken);
  const sent = await sendEmail({
    env,
    message: {
      to: email,
      subject: "Confirm your AI Newsy subscription",
      text: `Confirm your subscription: ${confirmUrl}`,
      html: `<p><a href="${confirmUrl}">Confirm your subscription</a></p>`,
    },
  });
  if (!sent.ok) {
    return json({ error: "confirmation email was not sent", reason: sent.reason || "" }, 502);
  }
  return json({ ok: true, status: "pending" }, 202);
}

async function confirm(request, env) {
  const token = new URL(request.url).searchParams.get("token") || "";
  if (!token) {
    return json({ error: "missing token" }, 400);
  }
  const result = await env.DB.prepare(
    `UPDATE subscribers SET confirmed = 1 WHERE confirm_token = ? AND confirmed = 0`
  )
    .bind(token)
    .run();
  const changes = result?.meta?.changes ?? result?.changes ?? 0;
  if (!changes) {
    return json({ error: "invalid token" }, 400);
  }
  return json({ ok: true, status: "confirmed" });
}

async function unsubscribe(request, env) {
  const url = new URL(request.url);
  let token = url.searchParams.get("token") || "";
  if (request.method === "POST") {
    const form = await request.text();
    const params = new URLSearchParams(form);
    token = params.get("token") || token;
  }
  const subscriberId = await verifyUnsubscribe(env.UNSUBSCRIBE_SECRET || "", token);
  if (!subscriberId) {
    return json({ error: "invalid token" }, 400);
  }
  await env.DB.prepare(
    `UPDATE subscribers SET unsubscribed_at = ? WHERE id = ? AND unsubscribed_at IS NULL`
  )
    .bind(new Date().toISOString(), Number(subscriberId))
    .run();
  return json({ ok: true, status: "unsubscribed" });
}

async function suppressBounce(request, env) {
  if (!authorized(request, env)) {
    return json({ error: "unauthorized" }, 401);
  }
  const payload = await request.json().catch(() => ({}));
  const email = String(payload.email || "").trim().toLowerCase();
  if (!email) {
    return json({ error: "email is required" }, 400);
  }
  await env.DB.prepare(`UPDATE subscribers SET suppressed_at = ? WHERE email = ?`)
    .bind(new Date().toISOString(), email)
    .run();
  return json({ ok: true, suppressed: email });
}

export async function runSendCron(env) {
  if (String(env.SEND_CRON_ENABLED || "") !== "1") {
    return { skipped: true, reason: "send-cron-disabled" };
  }
  const issue = await env.DB.prepare(
    `SELECT issue_id, digest_date, payload FROM issues ORDER BY published_at DESC LIMIT 1`
  ).first();
  if (!issue) {
    return { skipped: true, reason: "no-issue" };
  }
  const subscribers = await env.DB.prepare(
    `SELECT id, email FROM subscribers
     WHERE confirmed = 1 AND unsubscribed_at IS NULL AND suppressed_at IS NULL`
  ).all();
  let sent = 0;
  let skipped = 0;
  for (const subscriber of subscribers.results || []) {
    const key = idempotencyKey(issue.issue_id, subscriber.id);
    const token = await signUnsubscribe(env.UNSUBSCRIBE_SECRET || "", subscriber.id);
    const unsubscribeUrl = `${env.APP_URL || ""}/api/unsubscribe?token=${encodeURIComponent(token)}`;
    try {
      await env.DB.prepare(
        `INSERT INTO email_sends (issue_id, subscriber_id, idempotency_key, status, sent_at)
         VALUES (?, ?, ?, 'pending', ?)`
      )
        .bind(issue.issue_id, subscriber.id, key, new Date().toISOString())
        .run();
    } catch (_error) {
      skipped += 1;
      continue;
    }
    const result = await sendEmail({
      env,
      message: {
        to: subscriber.email,
        subject: `AI Newsy ${issue.digest_date}`,
        html: "<p>Your digest is ready.</p>",
        text: `AI Newsy ${issue.digest_date}`,
        idempotencyKey: key,
        headers: listUnsubscribeHeaders(unsubscribeUrl),
      },
    });
    if (result.ok) {
      sent += 1;
    }
  }
  return { skipped: false, sent, alreadySent: skipped };
}

export async function handleFetch(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname.startsWith("/issues/")) {
    return readIssueArchive(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/publish") {
    return publishIssue(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/subscribe") {
    return subscribe(request, env);
  }
  if (request.method === "GET" && url.pathname === "/api/confirm") {
    return confirm(request, env);
  }
  if ((request.method === "GET" || request.method === "POST") && url.pathname === "/api/unsubscribe") {
    return unsubscribe(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/webhooks/bounce") {
    return suppressBounce(request, env);
  }
  return json({ error: "not found" }, 404);
}

export default {
  fetch(request, env) {
    return handleFetch(request, env);
  },
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runSendCron(env));
  },
};

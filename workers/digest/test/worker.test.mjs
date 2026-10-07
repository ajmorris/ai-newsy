import assert from "node:assert/strict";
import test from "node:test";

import { handleFetch, runSendCron } from "../src/index.js";

function memoryDb() {
  const rows = { issues: [], subscribers: [], email_sends: [] };
  let nextId = 1;
  function prepare(sql) {
    const text = sql.replace(/\s+/g, " ").trim();
    let args = [];
    const statement = {
      bind(...bound) {
        args = bound;
        return statement;
      },
      async run() {
        if (text.startsWith("INSERT INTO issues")) {
          const [issueId, digestDate, payload, publishedAt] = args;
          const existing = rows.issues.find((row) => row.issue_id === issueId);
          if (existing) {
            Object.assign(existing, { digest_date: digestDate, payload, published_at: publishedAt });
          } else {
            rows.issues.push({ issue_id: issueId, digest_date: digestDate, payload, published_at: publishedAt });
          }
          return { success: true, meta: { changes: 1 } };
        }
        if (text.startsWith("INSERT INTO subscribers")) {
          const [email, confirmToken, subscribedAt] = args;
          if (rows.subscribers.some((row) => row.email === email)) {
            throw new Error("unique");
          }
          rows.subscribers.push({
            id: nextId,
            email,
            confirm_token: confirmToken,
            confirmed: 0,
            subscribed_at: subscribedAt,
            unsubscribed_at: null,
            suppressed_at: null,
          });
          nextId += 1;
          return { success: true, meta: { changes: 1 } };
        }
        if (text.startsWith("UPDATE subscribers SET confirmed")) {
          const [token] = args;
          const row = rows.subscribers.find((item) => item.confirm_token === token && item.confirmed === 0);
          if (!row) {
            return { success: true, meta: { changes: 0 } };
          }
          row.confirmed = 1;
          return { success: true, meta: { changes: 1 } };
        }
        if (text.startsWith("UPDATE subscribers SET unsubscribed_at")) {
          const [when, id] = args;
          const row = rows.subscribers.find((item) => item.id === id && item.unsubscribed_at == null);
          if (row) {
            row.unsubscribed_at = when;
          }
          return { success: true, meta: { changes: row ? 1 : 0 } };
        }
        if (text.startsWith("UPDATE subscribers SET suppressed_at")) {
          const [when, email] = args;
          const row = rows.subscribers.find((item) => item.email === email);
          if (row) {
            row.suppressed_at = when;
          }
          return { success: true, meta: { changes: row ? 1 : 0 } };
        }
        if (text.startsWith("INSERT INTO email_sends")) {
          const [issueId, subscriberId, key, sentAt] = args;
          if (rows.email_sends.some((row) => row.idempotency_key === key)) {
            throw new Error("unique");
          }
          rows.email_sends.push({
            issue_id: issueId,
            subscriber_id: subscriberId,
            idempotency_key: key,
            status: "pending",
            sent_at: sentAt,
          });
          return { success: true, meta: { changes: 1 } };
        }
        throw new Error(`unhandled sql: ${text}`);
      },
      async first() {
        if (text.startsWith("SELECT issue_id")) {
          return rows.issues[rows.issues.length - 1] || null;
        }
        return null;
      },
      async all() {
        if (text.includes("FROM subscribers")) {
          return {
            results: rows.subscribers.filter(
              (row) => row.confirmed === 1 && row.unsubscribed_at == null && row.suppressed_at == null
            ),
          };
        }
        return { results: [] };
      },
    };
    return statement;
  }
  return { prepare, rows };
}

function memoryBucket() {
  const objects = new Map();
  return {
    objects,
    async put(key, body) {
      objects.set(key, body);
    },
    async get(key) {
      if (!objects.has(key)) {
        return null;
      }
      return { body: objects.get(key) };
    },
  };
}

test("publish requires the bearer token and stores the issue", async () => {
  const env = { PUBLISH_TOKEN: "publish-secret", DB: memoryDb(), ISSUE_ARCHIVE: memoryBucket() };
  const denied = await handleFetch(
    new Request("https://worker.test/api/publish", {
      method: "POST",
      body: JSON.stringify({ issue_id: "20261007", digest_date: "2026-10-07" }),
    }),
    env
  );
  assert.equal(denied.status, 401);

  const accepted = await handleFetch(
    new Request("https://worker.test/api/publish", {
      method: "POST",
      headers: { Authorization: "Bearer publish-secret" },
      body: JSON.stringify({
        issue_id: "20261007",
        digest_date: "2026-10-07",
        archive_html: "<p>issue</p>",
      }),
    }),
    env
  );
  assert.equal(accepted.status, 200);
  assert.equal(env.DB.rows.issues.length, 1);
  assert.equal(env.ISSUE_ARCHIVE.objects.get("data/digests/2026-10-07.json")?.includes("20261007"), true);
  const archived = await handleFetch(new Request("https://worker.test/issues/2026-10-07.html"), env);
  assert.equal(archived.status, 200);
  assert.equal(await archived.text(), "<p>issue</p>");
});

test("double opt-in leaves the subscriber unconfirmed until the token is opened", async () => {
  const env = {
    PUBLISH_TOKEN: "publish-secret",
    DB: memoryDb(),
    RESEND_API_KEY: "re_test",
    EMAIL_FROM: "news@example.test",
  };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, status: 200 });
  try {
    const pending = await handleFetch(
      new Request("https://worker.test/api/subscribe", {
        method: "POST",
        body: JSON.stringify({ email: "Reader@Example.Test" }),
      }),
      env
    );
    assert.equal(pending.status, 202);
    assert.equal(env.DB.rows.subscribers[0].confirmed, 0);
    const token = env.DB.rows.subscribers[0].confirm_token;
    const confirmed = await handleFetch(new Request(`https://worker.test/api/confirm?token=${token}`), env);
    assert.equal(confirmed.status, 200);
    assert.equal(env.DB.rows.subscribers[0].confirmed, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("send cron stays off unless enabled and then skips a second pass", async () => {
  const env = {
    SEND_CRON_ENABLED: "0",
    DB: memoryDb(),
    UNSUBSCRIBE_SECRET: "secret",
    APP_URL: "https://example.test",
    RESEND_API_KEY: "re_test",
    EMAIL_FROM: "news@example.test",
  };
  const disabled = await runSendCron(env);
  assert.equal(disabled.reason, "send-cron-disabled");

  env.SEND_CRON_ENABLED = "1";
  env.DB.rows.issues.push({
    issue_id: "20261007",
    digest_date: "2026-10-07",
    payload: "{}",
    published_at: "2026-10-07T06:00:00Z",
  });
  env.DB.rows.subscribers.push({
    id: 4,
    email: "a@b.c",
    confirm_token: "t",
    confirmed: 1,
    unsubscribed_at: null,
    suppressed_at: null,
  });
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, status: 200 });
  try {
    const first = await runSendCron(env);
    const second = await runSendCron(env);
    assert.equal(first.sent, 1);
    assert.equal(second.alreadySent, 1);
    assert.equal(env.DB.rows.email_sends[0].idempotency_key, "20261007+4");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("a bounce suppresses the address", async () => {
  const env = { PUBLISH_TOKEN: "publish-secret", DB: memoryDb() };
  env.DB.rows.subscribers.push({
    id: 1,
    email: "a@b.c",
    confirm_token: "t",
    confirmed: 1,
    unsubscribed_at: null,
    suppressed_at: null,
  });
  const response = await handleFetch(
    new Request("https://worker.test/api/webhooks/bounce", {
      method: "POST",
      headers: { Authorization: "Bearer publish-secret" },
      body: JSON.stringify({ email: "a@b.c" }),
    }),
    env
  );
  assert.equal(response.status, 200);
  assert.ok(env.DB.rows.subscribers[0].suppressed_at);
});

import assert from "node:assert/strict";
import test from "node:test";

import { idempotencyKey, listUnsubscribeHeaders, sendEmail } from "../src/send-email.js";
import { signUnsubscribe, verifyUnsubscribe } from "../src/tokens.js";

test("idempotency key is issue plus subscriber", () => {
  assert.equal(idempotencyKey("20261007", 14), "20261007+14");
});

test("list unsubscribe headers are set for one-click", () => {
  const headers = listUnsubscribeHeaders("https://example.test/api/unsubscribe?token=abc");
  assert.match(headers["List-Unsubscribe"], /<https:\/\/example.test\/api\/unsubscribe\?token=abc>/);
  assert.equal(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
});

test("cloudflare adapter does not call the network", async () => {
  let called = false;
  const result = await sendEmail({
    env: { EMAIL_ADAPTER: "cloudflare", RESEND_API_KEY: "re_test" },
    message: { to: "a@b.c", subject: "Hi", html: "<p>Hi</p>" },
    fetchImpl: async () => {
      called = true;
      return { ok: true, status: 200 };
    },
  });
  assert.equal(called, false);
  assert.equal(result.adapter, "cloudflare");
  assert.equal(result.ok, false);
});

test("resend is the default and is skipped without a key", async () => {
  let called = false;
  const result = await sendEmail({
    env: {},
    message: { to: "a@b.c", subject: "Hi", html: "<p>Hi</p>" },
    fetchImpl: async () => {
      called = true;
      return { ok: true, status: 200 };
    },
  });
  assert.equal(called, false);
  assert.equal(result.adapter, "resend");
  assert.equal(result.reason, "missing-api-key");
});

test("resend adapter sends list-unsubscribe headers", async () => {
  let captured = null;
  const result = await sendEmail({
    env: { RESEND_API_KEY: "re_test", EMAIL_FROM: "news@example.test" },
    message: {
      to: "a@b.c",
      subject: "Hi",
      html: "<p>Hi</p>",
      idempotencyKey: "20261007+14",
      headers: listUnsubscribeHeaders("https://example.test/api/unsubscribe?token=abc"),
    },
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return { ok: true, status: 200 };
    },
  });
  assert.equal(result.ok, true);
  assert.equal(captured.url, "https://api.resend.com/emails");
  const body = JSON.parse(captured.options.body);
  assert.equal(body.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.equal(body.headers["Idempotency-Key"], "20261007+14");
});

test("unsubscribe tokens round-trip", async () => {
  const token = await signUnsubscribe("secret", 9);
  assert.equal(await verifyUnsubscribe("secret", token), "9");
  assert.equal(await verifyUnsubscribe("other", token), null);
});

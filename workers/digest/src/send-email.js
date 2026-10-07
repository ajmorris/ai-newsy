/**
 * sendEmail() picks an adapter. Resend stays the default until Cloudflare
 * Email Sending is generally available. The Cloudflare adapter is present
 * and does not send.
 */

export function idempotencyKey(issueId, subscriberId) {
  return `${issueId}+${subscriberId}`;
}

export function listUnsubscribeHeaders(unsubscribeUrl) {
  return {
    "List-Unsubscribe": `<${unsubscribeUrl}>`,
    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
  };
}

async function sendViaResend(env, message, fetchImpl) {
  if (!env.RESEND_API_KEY) {
    return { ok: false, adapter: "resend", reason: "missing-api-key" };
  }
  const response = await fetchImpl("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: env.EMAIL_FROM,
      to: message.to,
      subject: message.subject,
      html: message.html,
      text: message.text || "",
      headers: {
        ...(message.headers || {}),
        "Idempotency-Key": message.idempotencyKey || "",
      },
    }),
  });
  return { ok: response.ok, adapter: "resend", status: response.status };
}

function sendViaCloudflare() {
  return {
    ok: false,
    adapter: "cloudflare",
    reason: "cloudflare-email-sending-not-default",
  };
}

export async function sendEmail({ env, message, fetchImpl = fetch }) {
  const adapter = String(env.EMAIL_ADAPTER || "resend").toLowerCase();
  if (adapter === "cloudflare") {
    return sendViaCloudflare();
  }
  return sendViaResend(env, message, fetchImpl);
}

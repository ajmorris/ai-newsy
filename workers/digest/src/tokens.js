const encoder = new TextEncoder();

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function hmac(secret, value) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return hex(signature);
}

export async function signUnsubscribe(secret, subscriberId) {
  const id = String(subscriberId);
  const signature = await hmac(secret, id);
  return `${id}.${signature}`;
}

export async function verifyUnsubscribe(secret, token) {
  const [id, signature] = String(token || "").split(".");
  if (!id || !signature) {
    return null;
  }
  const expected = await hmac(secret, id);
  if (expected.length !== signature.length) {
    return null;
  }
  let mismatch = 0;
  for (let index = 0; index < expected.length; index += 1) {
    mismatch |= expected.charCodeAt(index) ^ signature.charCodeAt(index);
  }
  return mismatch === 0 ? id : null;
}

function getAppUrl() {
    const appUrl = process.env.APP_URL || '';
    if (!appUrl) {
        throw new Error('APP_URL is not configured.');
    }

    return appUrl.replace(/\/+$/, '');
}

export function buildConfirmationUrl(token) {
    const appUrl = getAppUrl();
    const url = new URL('/api/confirm', appUrl);
    url.searchParams.set('token', token);
    // #region agent log
    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6dec93'},body:JSON.stringify({sessionId:'6dec93',runId:'pre-fix',hypothesisId:'H1-H3',location:'frontend/api/lib/send-confirmation-email.js:31',message:'Built confirmation URL',data:{appUrlHost:new URL(appUrl).host,confirmUrlHost:url.host,confirmUrlPath:url.pathname,hasToken:Boolean(token),tokenLength:typeof token === 'string' ? token.length : 0},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    return url.toString();
}

export async function sendConfirmationEmail(email, token) {
    const fromEmail = process.env.EMAIL_FROM || '';
    if (!fromEmail) {
        throw new Error('EMAIL_FROM is not configured.');
    }
    const accountId = process.env.CLOUDFLARE_ACCOUNT_ID || '';
    if (!accountId) {
        throw new Error('CLOUDFLARE_ACCOUNT_ID is not configured.');
    }
    const apiToken = process.env.CLOUDFLARE_EMAIL_API_TOKEN || '';
    if (!apiToken) {
        throw new Error('CLOUDFLARE_EMAIL_API_TOKEN is not configured.');
    }

    const confirmUrl = buildConfirmationUrl(token);
    // #region agent log
    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6dec93'},body:JSON.stringify({sessionId:'6dec93',runId:'pre-fix',hypothesisId:'H1-H2',location:'frontend/api/lib/send-confirmation-email.js:45',message:'Sending confirmation email',data:{emailDomain:String(email).split('@')[1] || 'unknown',confirmUrlPath:new URL(confirmUrl).pathname,confirmUrlHasToken:new URL(confirmUrl).searchParams.has('token')},timestamp:Date.now()})}).catch(()=>{});
    // #endregion

    const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/email/sending/send`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${apiToken}`
        },
        body: JSON.stringify({
        from: {
            address: fromEmail,
            name: 'AI Newsy'
        },
        to: [email],
        subject: 'Confirm your AI Newsy subscription',
        html: `
            <div style="margin:0;padding:24px 16px;background:#0b0b0c;font-family:Inter,Arial,sans-serif;">
                <div style="max-width:640px;margin:0 auto;background:#17171a;border:1px solid #26262b;color:#f4f3ef;">
                    <div style="padding:24px 24px 18px;background:#121214;border-bottom:1px solid #1d1d21;">
                        <div style="display:inline-block;background:#39ff88;color:#0b0b0c;border-radius:2px;padding:4px 8px;font-family:'JetBrains Mono',Menlo,monospace;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                            AI Newsy
                        </div>
                        <h1 style="margin:14px 0 10px 0;font-size:30px;line-height:1.1;letter-spacing:-1px;color:#f4f3ef;">
                            Confirm your subscription.
                        </h1>
                        <p style="margin:0;color:#a3a099;font-size:14px;line-height:1.6;">
                            One click and you are in. We will send one concise AI digest each morning.
                        </p>
                    </div>
                    <div style="padding:22px 24px;">
                        <a
                            href="${confirmUrl}"
                            style="display:inline-block;background:#39ff88;color:#0b0b0c;text-decoration:none;padding:11px 16px;border-radius:2px;font-family:'JetBrains Mono',Menlo,monospace;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;box-shadow:0 0 20px rgba(57,255,136,0.4);"
                        >
                            Confirm subscription ->
                        </a>
                        <p style="margin:14px 0 0 0;color:#6b6a65;font-family:'JetBrains Mono',Menlo,monospace;font-size:10px;line-height:1.8;">
                            If this was not you, ignore this email.
                        </p>
                    </div>
                </div>
            </div>
        `,
        text: `Confirm your AI Newsy subscription: ${confirmUrl}`
        })
    });

    const payload = await response.json();
    if (!response.ok || !payload?.success) {
        throw new Error(`Cloudflare email send failed: ${JSON.stringify(payload?.errors || payload)}`);
    }
}

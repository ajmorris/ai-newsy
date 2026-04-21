import { Resend } from 'resend';

let resendClient = null;

function getResendClient() {
    if (resendClient) {
        return resendClient;
    }

    const apiKey = process.env.RESEND_API_KEY || '';
    if (!apiKey) {
        throw new Error('RESEND_API_KEY is not configured.');
    }

    resendClient = new Resend(apiKey);
    return resendClient;
}

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

    const confirmUrl = buildConfirmationUrl(token);
    const resend = getResendClient();
    // #region agent log
    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6dec93'},body:JSON.stringify({sessionId:'6dec93',runId:'pre-fix',hypothesisId:'H1-H2',location:'frontend/api/lib/send-confirmation-email.js:45',message:'Sending confirmation email',data:{emailDomain:String(email).split('@')[1] || 'unknown',confirmUrlPath:new URL(confirmUrl).pathname,confirmUrlHasToken:new URL(confirmUrl).searchParams.has('token')},timestamp:Date.now()})}).catch(()=>{});
    // #endregion

    await resend.emails.send({
        from: fromEmail,
        to: email,
        subject: 'Confirm your AI Newsy subscription',
        html: `
            <div style="font-family: Inter, Arial, sans-serif; max-width: 520px; margin: 0 auto; color: #111827;">
                <h1 style="font-size: 24px; margin-bottom: 12px;">Confirm your subscription</h1>
                <p style="font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
                    Click the button below to confirm you want to receive the AI Newsy daily digest.
                </p>
                <p style="margin-bottom: 24px;">
                    <a
                        href="${confirmUrl}"
                        style="background: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 8px; display: inline-block; font-weight: 600;"
                    >
                        Confirm subscription
                    </a>
                </p>
                <p style="font-size: 13px; color: #6b7280;">
                    If you did not request this, you can safely ignore this email.
                </p>
            </div>
        `,
        text: `Confirm your AI Newsy subscription: ${confirmUrl}`
    });
}

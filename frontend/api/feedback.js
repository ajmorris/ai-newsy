// Vercel Serverless Function: Feedback
// POST /api/feedback - Send feedback email via Resend

// Obfuscated recipient - assembled at runtime to avoid scraping
const _r = [97, 106, 64, 97, 106, 109, 111, 114, 114, 105, 115, 46, 109, 101];
function getRecipient() {
    return _r.map((c) => String.fromCharCode(c)).join('');
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { name, email, message, recaptchaToken } = req.body;

        // Validate fields
        if (!name || !email || !message) {
            return res.status(400).json({ error: 'All fields are required.' });
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return res.status(400).json({ error: 'Invalid email address.' });
        }

        // Verify reCAPTCHA
        const recaptchaSecret = process.env.RECAPTCHA_SECRET_KEY;
        if (recaptchaSecret) {
            if (!recaptchaToken) {
                return res.status(400).json({ error: 'reCAPTCHA verification failed.' });
            }

            const verifyUrl = 'https://www.google.com/recaptcha/api/siteverify';
            const verifyRes = await fetch(verifyUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `secret=${encodeURIComponent(recaptchaSecret)}&response=${encodeURIComponent(recaptchaToken)}`,
            });
            const verifyData = await verifyRes.json();

            if (!verifyData.success || (verifyData.score !== undefined && verifyData.score < 0.5)) {
                return res.status(400).json({ error: 'reCAPTCHA verification failed. Please try again.' });
            }
        }

        // Send email via Resend
        const resendKey = process.env.RESEND_API_KEY;
        if (!resendKey) {
            console.error('RESEND_API_KEY not configured');
            return res.status(500).json({ error: 'Email service not configured.' });
        }

        const emailFrom = process.env.EMAIL_FROM || 'AI Newsy <noreply@ainewsy.com>';
        const recipient = getRecipient();

        const sendRes = await fetch('https://api.resend.com/emails', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${resendKey}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                from: emailFrom,
                to: [recipient],
                subject: `AI Newsy Feedback from ${name}`,
                reply_to: email,
                html: `
                    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #6366f1;">New Feedback from AI Newsy</h2>
                        <p><strong>Name:</strong> ${escapeHtml(name)}</p>
                        <p><strong>Email:</strong> ${escapeHtml(email)}</p>
                        <hr style="border: 1px solid #eee;">
                        <p style="white-space: pre-wrap;">${escapeHtml(message)}</p>
                    </div>
                `,
            }),
        });

        if (!sendRes.ok) {
            const errData = await sendRes.json().catch(() => ({}));
            console.error('Resend error:', errData);
            return res.status(500).json({ error: 'Failed to send feedback. Please try again.' });
        }

        return res.status(200).json({ message: 'Feedback sent successfully!' });
    } catch (error) {
        console.error('Feedback error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}

function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

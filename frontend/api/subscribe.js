// Vercel Serverless Function: Subscribe
// POST /api/subscribe - Add a new email subscriber

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL || '';
const supabaseSecretKey = process.env.SUPABASE_SECRET_KEY || '';

const supabase = createClient(
    supabaseUrl,
    supabaseSecretKey
);

const RATE_LIMIT_WINDOW_MS = Number(process.env.SUBSCRIBE_RATE_LIMIT_WINDOW_MS || 10 * 60 * 1000);
const RATE_LIMIT_MAX_REQUESTS = Number(process.env.SUBSCRIBE_RATE_LIMIT_MAX_REQUESTS || 5);
const rateLimitStore = new Map();

function getClientIp(req) {
    const forwarded = req.headers['x-forwarded-for'];
    if (typeof forwarded === 'string' && forwarded.length > 0) {
        return forwarded.split(',')[0].trim();
    }

    return req.socket?.remoteAddress || 'unknown';
}

function isRateLimited(clientIp) {
    const now = Date.now();
    const existing = rateLimitStore.get(clientIp);

    if (!existing || now > existing.expiresAt) {
        rateLimitStore.set(clientIp, {
            count: 1,
            expiresAt: now + RATE_LIMIT_WINDOW_MS
        });
        return false;
    }

    existing.count += 1;
    if (existing.count > RATE_LIMIT_MAX_REQUESTS) {
        return true;
    }

    return false;
}

function cleanupRateLimitEntries() {
    const now = Date.now();
    for (const [key, value] of rateLimitStore.entries()) {
        if (now > value.expiresAt) {
            rateLimitStore.delete(key);
        }
    }
}

async function verifyTurnstileToken(token, remoteIp) {
    const secret = process.env.TURNSTILE_SECRET_KEY;
    if (!secret) {
        return { enabled: false, ok: true };
    }

    if (!token || token.trim() === '') {
        return { enabled: true, ok: false, reason: 'missing token' };
    }

    const body = new URLSearchParams({
        secret,
        response: token,
        remoteip: remoteIp
    });

    const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
    });

    if (!response.ok) {
        return { enabled: true, ok: false, reason: `turnstile status ${response.status}` };
    }

    const result = await response.json();
    return {
        enabled: true,
        ok: Boolean(result.success),
        reason: Array.isArray(result['error-codes']) ? result['error-codes'].join(',') : undefined
    };
}

async function verifyHCaptchaToken(token, remoteIp) {
    const secret = process.env.HCAPTCHA_SECRET_KEY;
    if (!secret) {
        return { enabled: false, ok: true };
    }

    if (!token || token.trim() === '') {
        return { enabled: true, ok: false, reason: 'missing token' };
    }

    const body = new URLSearchParams({
        secret,
        response: token,
        remoteip: remoteIp
    });

    const response = await fetch('https://hcaptcha.com/siteverify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
    });

    if (!response.ok) {
        return { enabled: true, ok: false, reason: `hcaptcha status ${response.status}` };
    }

    const result = await response.json();
    return {
        enabled: true,
        ok: Boolean(result.success),
        reason: Array.isArray(result['error-codes']) ? result['error-codes'].join(',') : undefined
    };
}

async function verifyCaptcha({ token, provider, remoteIp }) {
    const normalizedProvider = String(provider || '').toLowerCase().trim();

    if (normalizedProvider === 'hcaptcha') {
        return verifyHCaptchaToken(token, remoteIp);
    }

    if (normalizedProvider === 'turnstile') {
        return verifyTurnstileToken(token, remoteIp);
    }

    // If provider is not explicitly set, prefer Turnstile when configured.
    const turnstileResult = await verifyTurnstileToken(token, remoteIp);
    if (turnstileResult.enabled) {
        return turnstileResult;
    }

    return verifyHCaptchaToken(token, remoteIp);
}

async function sendSlackSignupNotification(email) {
    const webhookUrl = process.env.SLACK_WEBHOOK_URL;

    if (!webhookUrl) {
        console.warn('SLACK_WEBHOOK_URL is not set. Skipping Slack notification.');
        return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1500);

    try {
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: `New newsletter signup: ${email}`,
                blocks: [
                    {
                        type: 'section',
                        text: {
                            type: 'mrkdwn',
                            text: `*New newsletter signup*\n• Email: ${email}\n• Source: AI Newsy signup API\n• Time: ${new Date().toISOString()}`
                        }
                    }
                ]
            }),
            signal: controller.signal
        });

        if (!response.ok) {
            console.error('Slack webhook failed with status:', response.status);
        }
    } catch (error) {
        console.error('Slack notification error:', error);
    } finally {
        clearTimeout(timeoutId);
    }
}

function generateToken() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let token = '';
    for (let i = 0; i < 43; i++) {
        token += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return token;
}

export default async function handler(req, res) {
    // CORS headers
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
        if (!supabaseUrl || !supabaseSecretKey) {
            console.error('SUPABASE_URL or SUPABASE_SECRET_KEY not configured for subscribe API.');
            return res.status(500).json({ error: 'Subscription service is not configured.' });
        }

        cleanupRateLimitEntries();

        const clientIp = getClientIp(req);
        if (isRateLimited(clientIp)) {
            return res.status(429).json({ error: 'Too many signup attempts. Please try again shortly.' });
        }

        const { email, website, captchaToken, captchaProvider } = req.body || {};

        // Honeypot: bots often fill hidden fields. Return success-like response silently.
        if (website && String(website).trim() !== '') {
            return res.status(200).json({
                message: 'Successfully subscribed! Welcome to AI Newsy.',
                status: 'confirmed'
            });
        }

        // Validate email
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return res.status(400).json({ error: 'Invalid email address' });
        }

        const normalizedEmail = email.toLowerCase().trim();
        const captchaCheck = await verifyCaptcha({
            token: String(captchaToken || ''),
            provider: String(captchaProvider || ''),
            remoteIp: clientIp
        });

        if (captchaCheck.enabled && !captchaCheck.ok) {
            console.warn('Captcha verification failed:', captchaCheck.reason || 'unknown');
            return res.status(400).json({ error: 'Captcha verification failed. Please try again.' });
        }

        // Check if already subscribed
        const { data: existing } = await supabase
            .from('subscribers')
            .select('id, confirmed')
            .eq('email', normalizedEmail)
            .single();

        if (existing) {
            if (existing.confirmed) {
                return res.status(400).json({ error: 'This email is already subscribed!' });
            } else {
                return res.status(200).json({
                    message: 'Check your email to confirm your subscription!',
                    status: 'pending'
                });
            }
        }

        // Create new subscriber
        const confirmToken = generateToken();

        const { data, error } = await supabase
            .from('subscribers')
            .insert({
                email: normalizedEmail,
                confirm_token: confirmToken,
                confirmed: true,  // Auto-confirm for now (no email verification flow)
                subscribed_at: new Date().toISOString()
            })
            .select()
            .single();

        if (error) {
            console.error('Supabase error:', error);
            return res.status(500).json({ error: 'Failed to subscribe. Please try again.' });
        }

        // Best-effort side effect: never fail successful signup on Slack issues.
        await sendSlackSignupNotification(normalizedEmail);

        return res.status(200).json({
            message: 'Successfully subscribed! Welcome to AI Newsy.',
            status: 'confirmed'
        });

    } catch (error) {
        console.error('Subscribe error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}

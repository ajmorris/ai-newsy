// Vercel Serverless Function: Unsubscribe
// GET /api/unsubscribe?token=xxx - Unsubscribe from newsletter

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL || '';
const supabaseSecretKey = process.env.SUPABASE_SECRET_KEY || '';

const supabase = createClient(
    supabaseUrl,
    supabaseSecretKey
);

export default async function handler(req, res) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const rawToken = req.query?.token;
    const token = Array.isArray(rawToken) ? rawToken[0] : rawToken;

    if (!token) {
        console.warn('Unsubscribe request missing token.', { url: req.url || '' });
        return res.status(400).send(renderPage('Missing Token', 'Invalid unsubscribe link.', 'error'));
    }

    try {
        if (!supabaseUrl || !supabaseSecretKey) {
            console.error('SUPABASE_URL or SUPABASE_SECRET_KEY not configured for unsubscribe API.');
            return res.status(500).send(renderPage('Error', 'Unsubscribe service is not configured.', 'error'));
        }

        const { data, error } = await supabase
            .from('subscribers')
            .update({ unsubscribed_at: new Date().toISOString() })
            .eq('confirm_token', token)
            .is('unsubscribed_at', null)
            .select()
            .single();

        if (error || !data) {
            console.warn('Unsubscribe request failed to match active subscriber.', {
                hasError: Boolean(error),
                errorCode: error?.code || null,
                url: req.url || '',
            });
            return res.status(400).send(renderPage(
                'Already Unsubscribed',
                'This email has already been unsubscribed or the link is invalid.',
                'info'
            ));
        }

        return res.status(200).send(renderPage(
            'Unsubscribed',
            "You've been unsubscribed from AI Newsy. We're sorry to see you go!",
            'success'
        ));

    } catch (error) {
        console.error('Unsubscribe error:', error);
        return res.status(500).send(renderPage('Error', 'Something went wrong. Please try again.', 'error'));
    }
}

function renderPage(title, message, type) {
    const colors = {
        success: '#34d399',
        error: '#f87171',
        info: '#60a5fa'
    };

    return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>${title} - AI Newsy</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Inter', sans-serif;
                background: #0a0a0f;
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
                padding: 20px;
            }
            .container {
                text-align: center;
                max-width: 400px;
            }
            .icon {
                font-size: 64px;
                margin-bottom: 24px;
            }
            h1 {
                color: ${colors[type]};
                margin-bottom: 16px;
            }
            p {
                color: #9ca3af;
                line-height: 1.6;
            }
            a {
                display: inline-block;
                margin-top: 24px;
                color: #818cf8;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">${type === 'success' ? '👋' : type === 'error' ? '❌' : 'ℹ️'}</div>
            <h1>${title}</h1>
            <p>${message}</p>
            <a href="/">← Back to AI Newsy</a>
        </div>
    </body>
    </html>
    `;
}

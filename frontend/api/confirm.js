import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL || '';
const supabaseSecretKey = process.env.SUPABASE_SECRET_KEY || '';

const supabase = createClient(
    supabaseUrl,
    supabaseSecretKey
);

export default async function handler(req, res) {
    // #region agent log
    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6dec93'},body:JSON.stringify({sessionId:'6dec93',runId:'pre-fix',hypothesisId:'H2-H4',location:'frontend/api/confirm.js:13',message:'Confirm endpoint invoked',data:{method:req.method,hasToken:Boolean(req.query && req.query.token),url:req.url || ''},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { token } = req.query;

    if (!token) {
        return res.status(400).send(renderPage('Missing Token', 'Invalid confirmation link.', 'error'));
    }

    try {
        if (!supabaseUrl || !supabaseSecretKey) {
            console.error('SUPABASE_URL or SUPABASE_SECRET_KEY not configured for confirm API.');
            return res.status(500).send(renderPage('Error', 'Confirmation service is not configured.', 'error'));
        }

        const { data, error } = await supabase
            .from('subscribers')
            .update({ confirmed: true })
            .eq('confirm_token', token)
            .eq('confirmed', false)
            .select()
            .single();
        // #region agent log
        fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6dec93'},body:JSON.stringify({sessionId:'6dec93',runId:'pre-fix',hypothesisId:'H5',location:'frontend/api/confirm.js:39',message:'Confirm DB update result',data:{hasData:Boolean(data),hasError:Boolean(error),errorCode:error?.code || null,errorMessage:error?.message || null},timestamp:Date.now()})}).catch(()=>{});
        // #endregion

        if (error || !data) {
            return res.status(400).send(renderPage(
                'Already Confirmed',
                'This subscription is already confirmed or the link is invalid.',
                'info'
            ));
        }

        return res.status(200).send(renderPage(
            'Subscription Confirmed',
            "You're all set. You'll start receiving AI Newsy updates soon.",
            'success'
        ));
    } catch (error) {
        console.error('Confirm error:', error);
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
            <div class="icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</div>
            <h1>${title}</h1>
            <p>${message}</p>
            <a href="/">← Back to AI Newsy</a>
        </div>
    </body>
    </html>
    `;
}

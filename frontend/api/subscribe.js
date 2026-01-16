// Vercel Serverless Function: Subscribe
// POST /api/subscribe - Add a new email subscriber

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_KEY
);

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
        const { email } = req.body;

        // Validate email
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return res.status(400).json({ error: 'Invalid email address' });
        }

        const normalizedEmail = email.toLowerCase().trim();

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

        return res.status(200).json({
            message: 'Successfully subscribed! Welcome to AI Newsy.',
            status: 'confirmed'
        });

    } catch (error) {
        console.error('Subscribe error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}

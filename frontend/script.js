document.addEventListener('DOMContentLoaded', () => {
    const forms = Array.from(document.querySelectorAll('.subscribe-form'));
    const navSubscribeButton = document.getElementById('nav-subscribe-btn');
    const recentIssuesList = document.getElementById('recent-issues-list');
    const globalMessageEl = document.getElementById('form-message');
    const captchaContainer = document.getElementById('captcha-container');
    const hcaptchaWidget = document.getElementById('hcaptcha-widget');
    const hcaptchaSiteKey = (
        window.HCAPTCHA_SITE_KEY ||
        document.querySelector('meta[name="hcaptcha-site-key"]')?.content ||
        document.documentElement.getAttribute('data-hcaptcha-site-key') ||
        ''
    ).trim();
    const captchaState = {
        required: Boolean(hcaptchaSiteKey),
        ready: false,
        solved: false,
        widgetId: null,
        loadError: false,
    };

    loadRecentIssues();

    function setCaptchaToken(token, provider) {
        forms.forEach((form) => {
            const tokenInput = form.querySelector('input[name="captchaToken"]');
            const providerInput = form.querySelector('input[name="captchaProvider"]');
            if (tokenInput) {
                tokenInput.value = token || '';
            }
            if (providerInput) {
                providerInput.value = provider || '';
            }
        });
    }

    function showGlobalMessage(text, type) {
        if (!globalMessageEl) {
            return;
        }
        globalMessageEl.textContent = text;
        globalMessageEl.className = `form-message ${type}`;
    }

    window.onTurnstileSuccess = (token) => setCaptchaToken(token, 'turnstile');
    window.onTurnstileExpired = () => setCaptchaToken('', 'turnstile');
    window.onHCaptchaSuccess = (token) => {
        captchaState.solved = Boolean(token);
        setCaptchaToken(token, 'hcaptcha');
    };
    window.onHCaptchaExpired = () => {
        captchaState.solved = false;
        setCaptchaToken('', 'hcaptcha');
    };
    window.onHCaptchaError = () => {
        captchaState.loadError = true;
        captchaState.solved = false;
        setCaptchaToken('', 'hcaptcha');
        showGlobalMessage('Captcha failed to load. You can still continue; anti-spam checks remain active.', 'error');
    };
    window.onHCaptchaApiLoad = () => {
        if (!captchaState.required || !hcaptchaWidget || !window.hcaptcha) {
            return;
        }

        if (captchaContainer) {
            captchaContainer.hidden = false;
        }

        captchaState.widgetId = window.hcaptcha.render(hcaptchaWidget, {
            sitekey: hcaptchaSiteKey,
            callback: window.onHCaptchaSuccess,
            'expired-callback': window.onHCaptchaExpired,
            'error-callback': window.onHCaptchaError,
        });
        captchaState.ready = true;
    };

    if (!captchaState.required && captchaContainer) {
        captchaContainer.hidden = true;
    }

    if (navSubscribeButton) {
        navSubscribeButton.addEventListener('click', () => {
            const cta = document.getElementById('cta-subscribe');
            if (cta) {
                cta.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    }

    forms.forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const emailInput = form.querySelector('input[name="email"]');
            const websiteInput = form.querySelector('input[name="website"]');
            const submitButton = form.querySelector('.submit-btn');
            const formMeta = form.querySelector('.form-meta');
            const successPanel = form.querySelector('.form-success');
            const successBody = form.querySelector('.success-body');
            const subscribeRow = form.querySelector('.subscribe-row');

            if (!emailInput || !submitButton || !formMeta || !successPanel || !successBody || !subscribeRow) {
                return;
            }

            const email = emailInput.value.trim();
            const honeypotValue = websiteInput ? websiteInput.value : '';
            const captchaToken = (form.querySelector('input[name="captchaToken"]') || {}).value || '';
            const captchaProvider = (form.querySelector('input[name="captchaProvider"]') || {}).value || '';

            form.classList.remove('form-error');
            form.classList.remove('form-success-state');
            formMeta.textContent = '» free · one email / day · unsub anytime';
            successPanel.hidden = true;
            subscribeRow.hidden = false;
            showGlobalMessage('', '');

            if (!email) {
                applyErrorState(form, formMeta, 'Field required.');
                return;
            }
            if (!isValidEmail(email)) {
                applyErrorState(form, formMeta, 'Invalid email format.');
                return;
            }
            if (captchaState.required && !captchaState.loadError && (!captchaState.ready || !captchaState.solved || !captchaToken)) {
                applyErrorState(form, formMeta, 'Please complete the captcha before subscribing.');
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = 'Sending...';

            try {
                const response = await fetch('/api/subscribe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email,
                        website: honeypotValue,
                        captchaToken,
                        captchaProvider,
                    }),
                });

                const contentType = (response.headers.get('content-type') || '').toLowerCase();
                let data = {};
                if (contentType.includes('application/json')) {
                    data = await response.json();
                } else {
                    const rawText = await response.text();
                    data = { error: rawText || 'Unexpected server response.' };
                }

                if (!response.ok) {
                    applyErrorState(form, formMeta, data.error || `Request failed (${response.status}). Try again.`);
                    return;
                }

                form.classList.add('form-success-state');
                subscribeRow.hidden = true;
                successPanel.hidden = false;

                if (data.status === 'already-subscribed') {
                    successBody.textContent = `Already subscribed. You are on the AI Newsy list. - ${email}`;
                } else if (data.status === 'confirmed') {
                    successBody.textContent = `Subscription confirmed. Welcome to AI Newsy. - ${email}`;
                } else {
                    successBody.textContent = `Confirmation sent. Check your inbox. - ${email}`;
                }

                emailInput.value = '';
                if (websiteInput) {
                    websiteInput.value = '';
                }
                setCaptchaToken('', captchaProvider);
                captchaState.solved = false;
                if (window.hcaptcha && typeof captchaState.widgetId === 'number') {
                    window.hcaptcha.reset(captchaState.widgetId);
                }
            } catch (error) {
                console.error('Subscription error:', error);
                applyErrorState(form, formMeta, 'Network error. Try again.');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Subscribe ↵';
            }
        });
    });

    function applyErrorState(form, formMeta, message) {
        form.classList.add('form-error');
        formMeta.textContent = `» error: ${message}`;
    }

    function isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    async function loadRecentIssues() {
        if (!recentIssuesList) {
            return;
        }

        try {
            const response = await fetch(`/issues/index.json?ts=${Date.now()}`, {
                cache: 'no-store',
                headers: {
                    Accept: 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load archive manifest.');
            }

            const data = await response.json();
            const mergedIssues = await mergeIssuesFromArchive(data);
            renderRecentIssues(mergedIssues);
        } catch (error) {
            console.error('Issue archive load error:', error);
            try {
                const fallbackIssues = await loadIssuesFromArchiveHtml();
                if (fallbackIssues.length > 0) {
                    renderRecentIssues(fallbackIssues);
                    return;
                }
            } catch (fallbackError) {
                console.error('Archive HTML fallback failed:', fallbackError);
            }
            recentIssuesList.innerHTML = '<li class="issues-loading">No issues published yet. Check back soon.</li>';
        }
    }

    function shortSubject(value) {
        let text = String(value || '').replace(/\s+/g, ' ').trim();
        if (!text) {
            return '';
        }

        const parts = text.split(/\s+[—–]\s+|:\s+/);
        let lead = parts[0];
        const rest = parts.length > 1 ? parts[1] : '';
        if (rest && /\b(biggest|sounds like|thriller|kind of week)\b/i.test(lead)) {
            lead = rest;
        }
        lead = lead.replace(/\btoday\b/gi, ' ').replace(/\s+/g, ' ').trim();
        const thatSplit = lead.split(/\s+that\s+/i);
        if (thatSplit.length > 1 && thatSplit[0].split(' ').length > 6) {
            lead = thatSplit.slice(1).join(' that ');
        }
        if (lead.split(' ').length > 8 && lead.includes(',')) {
            const clauses = lead.split(',');
            const firstClause = clauses[0].trim();
            const nextClause = clauses.slice(1).join(',').trim();
            if (firstClause.split(' ').length > 8 && /^it\b/i.test(nextClause)) {
                lead = nextClause;
            } else if (firstClause.split(' ').length >= 3) {
                lead = firstClause;
            }
        }

        const skip = new Set(['is', 'are', 'was', 'were', 'just']);
        const stop = new Set(['around', 'after', 'while', 'even', 'during', 'before', 'into', 'over', 'for', 'in']);
        const dangling = new Set(['a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'for', 'with', 'as', 'that', 'from', 'by', 'its', 'their', 'what', 'like']);
        const words = [];
        lead.replace(/[.,]+$/g, '').split(' ').forEach((word) => {
            const cleaned = word.replace(/^[.,]+|[.,]+$/g, '');
            const bare = cleaned.replace(/[^A-Za-z0-9']/g, '').toLowerCase();
            if (!bare) {
                return;
            }
            if (words.length && skip.has(bare)) {
                return;
            }
            words.push(cleaned);
        });

        const bareWord = (word) => word.replace(/[^A-Za-z0-9']/g, '').toLowerCase();
        let kept = words.slice();
        const stopAt = words.findIndex((word, index) => index >= 3 && stop.has(bareWord(word)));
        if (stopAt !== -1) {
            kept = words.slice(0, stopAt);
        } else if (words.length > 9) {
            kept = words.slice(0, 8);
        }
        const conjunctionAt = kept.findIndex((word, index) => index >= 4 && /^(and|or)$/i.test(bareWord(word)));
        if (conjunctionAt !== -1) {
            kept = kept.slice(0, conjunctionAt);
        }
        while (kept.length > 3 && dangling.has(bareWord(kept[kept.length - 1]))) {
            kept.pop();
        }

        let subject = kept.join(' ').trim();
        if (!subject) {
            return '';
        }
        if (/^it\b/i.test(subject) && /\bclaude\b/i.test(text)) {
            subject = subject.replace(/^it\b/i, 'Claude');
        }
        return subject.charAt(0).toUpperCase() + subject.slice(1);
    }

    function editionSubject(issue) {
        const fromIntro = shortSubject(issue && issue.intro);
        if (fromIntro) {
            return fromIntro;
        }
        const subject = String((issue && issue.subject) || '').trim();
        if (subject && !/^ISSUE\s+\d+/i.test(subject)) {
            return shortSubject(subject) || 'Daily briefing';
        }
        return 'Daily briefing';
    }

    function issueDateLabel(issue) {
        const slug = String((issue && (issue.digestDate || issue.slug)) || '');
        const match = slug.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!match) {
            return 'Issue';
        }
        return `Issue ${Number(match[2])}/${Number(match[3])}/${match[1]}:`;
    }

    function renderRecentIssues(recentIssues) {
        if (!Array.isArray(recentIssues) || recentIssues.length === 0) {
            recentIssuesList.innerHTML = '<li class="issues-loading">No recent issues found yet.</li>';
            return;
        }

        const items = recentIssues
            .map((issue) => {
                const headline = escapeHtml(editionSubject(issue));
                const dateLabel = escapeHtml(issueDateLabel(issue));
                const articleCount = Number.isFinite(issue.articleCount) ? `${issue.articleCount} stories` : '';
                const safeUrl = issue.urlPath || '/issues/';
                return `<li>
                    <span class="mono archive-date">${dateLabel}</span>
                    <a class="archive-headline" href="${safeUrl}">${headline}</a>
                    <span class="mono archive-count">${escapeHtml(articleCount)}</span>
                    <span class="archive-chevron">→</span>
                </li>`;
            })
            .join('');

        recentIssuesList.innerHTML = items;
    }

    async function mergeIssuesFromArchive(manifestData) {
        const manifestIssues = Array.isArray(manifestData && manifestData.recentIssues)
            ? manifestData.recentIssues
            : [];
        const htmlIssues = await loadIssuesFromArchiveHtml();
        if (htmlIssues.length === 0) {
            return manifestIssues;
        }

        const bySlug = new Map();
        manifestIssues.forEach((issue) => {
            const slug = normalizeIssueSlug(issue && issue.slug, issue && issue.urlPath);
            if (!slug) {
                return;
            }
            bySlug.set(slug, {
                ...issue,
                slug,
                digestDate: issue.digestDate || slug,
                urlPath: issue.urlPath || `/issues/${slug}.html`,
            });
        });

        htmlIssues.forEach((issue) => {
            const slug = normalizeIssueSlug(issue.slug, issue.urlPath);
            if (!slug || bySlug.has(slug)) {
                return;
            }
            bySlug.set(slug, {
                ...issue,
                slug,
                digestDate: issue.digestDate || slug,
                urlPath: issue.urlPath || `/issues/${slug}.html`,
            });
        });

        return Array.from(bySlug.values())
            .sort((a, b) => {
                const aDate = String(a.digestDate || a.slug || '');
                const bDate = String(b.digestDate || b.slug || '');
                return bDate.localeCompare(aDate);
            })
            .slice(0, 12);
    }

    async function loadIssuesFromArchiveHtml() {
        const response = await fetch(`/issues/index.html?ts=${Date.now()}`, {
            cache: 'no-store',
            headers: {
                Accept: 'text/html',
            },
        });
        if (!response.ok) {
            throw new Error(`Failed to load /issues/index.html (${response.status})`);
        }
        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const anchors = Array.from(doc.querySelectorAll('li a[href$=".html"]'));
        const issues = anchors
            .map((anchor) => {
                const href = anchor.getAttribute('href') || '';
                const normalizedHref = href.startsWith('/issues/') ? href : `/issues/${href.replace(/^\//, '')}`;
                const slugMatch = normalizedHref.match(/\/issues\/(\d{4}-\d{2}-\d{2})\.html$/);
                if (!slugMatch) {
                    return null;
                }
                const slug = slugMatch[1];
                const row = anchor.closest('li');
                const dateEl = row ? row.querySelector('.issue-date') : null;
                const countEl = row ? row.querySelector('.story-count') : null;
                const countText = countEl ? countEl.textContent : (row ? (row.textContent || '') : '');
                const countMatch = countText.match(/(\d+)\s+stories/i);
                return {
                    slug,
                    digestDate: slug,
                    displayDate: dateEl ? dateEl.textContent.trim() : slug,
                    subject: anchor.textContent.trim(),
                    articleCount: countMatch ? Number(countMatch[1]) : undefined,
                    urlPath: normalizedHref,
                };
            })
            .filter(Boolean);
        return issues;
    }

    function normalizeIssueSlug(slug, urlPath) {
        const rawSlug = String(slug || '').trim();
        if (/^\d{4}-\d{2}-\d{2}$/.test(rawSlug)) {
            return rawSlug;
        }
        const rawPath = String(urlPath || '').trim();
        const match = rawPath.match(/(\d{4}-\d{2}-\d{2})\.html$/);
        return match ? match[1] : '';
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

});

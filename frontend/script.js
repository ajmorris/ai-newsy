document.addEventListener('DOMContentLoaded', () => {
    const forms = Array.from(document.querySelectorAll('.subscribe-form'));
    const navSubscribeButton = document.getElementById('nav-subscribe-btn');
    const recentIssuesList = document.getElementById('recent-issues-list');
    const nextIssueNumberEl = document.getElementById('next-issue-number');
    const nextIssueCountdownEl = document.getElementById('next-issue-countdown');
    const globalMessageEl = document.getElementById('form-message');
    const captchaContainer = document.getElementById('captcha-container');
    const hcaptchaWidget = document.getElementById('hcaptcha-widget');
    const NEWSLETTER_TIME_ZONE = 'America/New_York';
    const FALLBACK_ISSUE_NUMBER = '001';
    const COUNTDOWN_FALLBACK_TEXT = 'ships daily at 5:00 AM ET';
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
    initializeHeroCountdown();

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
            updateHeroIssueNumber(data, mergedIssues);
        } catch (error) {
            console.error('Issue archive load error:', error);
            try {
                const fallbackIssues = await loadIssuesFromArchiveHtml();
                if (fallbackIssues.length > 0) {
                    renderRecentIssues(fallbackIssues);
                    updateHeroIssueNumber(null, fallbackIssues);
                    return;
                }
            } catch (fallbackError) {
                console.error('Archive HTML fallback failed:', fallbackError);
            }
            recentIssuesList.innerHTML = '<li class="issues-loading">No issues published yet. Check back soon.</li>';
            updateHeroIssueNumber(null, []);
        }
    }

    function initializeHeroCountdown() {
        if (!nextIssueCountdownEl) {
            return;
        }

        updateHeroCountdown();
        setInterval(updateHeroCountdown, 60 * 1000);
    }

    function updateHeroIssueNumber(manifestData, renderedIssues = []) {
        if (!nextIssueNumberEl) {
            return;
        }

        const manifestCount = Number(manifestData && manifestData.issueCount);
        const derivedCount = Array.isArray(renderedIssues) ? renderedIssues.length : 0;
        const issueCount = Number.isFinite(manifestCount) && manifestCount >= derivedCount
            ? manifestCount
            : derivedCount;
        if (!Number.isFinite(issueCount) || issueCount < 0) {
            nextIssueNumberEl.textContent = FALLBACK_ISSUE_NUMBER;
            return;
        }

        const nextIssue = issueCount + 1;
        nextIssueNumberEl.textContent = String(nextIssue).padStart(3, '0');
    }

    function updateHeroCountdown() {
        try {
            const minutesRemaining = getMinutesUntilNextSend();
            const hours = Math.floor(minutesRemaining / 60);
            const minutes = minutesRemaining % 60;
            nextIssueCountdownEl.textContent = `ships in ${hours}h ${minutes}m`;
        } catch (error) {
            console.error('Countdown update error:', error);
            nextIssueCountdownEl.textContent = COUNTDOWN_FALLBACK_TEXT;
        }
    }

    function getMinutesUntilNextSend() {
        const now = new Date();
        const nowInNewsletterTz = new Date(
            now.toLocaleString('en-US', { timeZone: NEWSLETTER_TIME_ZONE })
        );

        const nextSendInNewsletterTz = new Date(nowInNewsletterTz);
        nextSendInNewsletterTz.setHours(5, 0, 0, 0);
        if (nowInNewsletterTz >= nextSendInNewsletterTz) {
            nextSendInNewsletterTz.setDate(nextSendInNewsletterTz.getDate() + 1);
        }

        const msRemaining = nextSendInNewsletterTz.getTime() - nowInNewsletterTz.getTime();
        return Math.max(0, Math.floor(msRemaining / (60 * 1000)));
    }

    function renderRecentIssues(recentIssues) {
        if (!Array.isArray(recentIssues) || recentIssues.length === 0) {
            recentIssuesList.innerHTML = '<li class="issues-loading">No recent issues found yet.</li>';
            return;
        }

        const items = recentIssues
            .map((issue) => {
                const subject = escapeHtml(issue.subject || 'Untitled issue');
                const displayDate = escapeHtml(issue.displayDate || issue.digestDate || '');
                const articleCount = Number.isFinite(issue.articleCount) ? `${issue.articleCount} stories` : '';
                const issueNumber = escapeHtml(
                    issue.issueNumber || (issue.slug ? issue.slug.replace(/[^0-9]/g, '').slice(-5) : '')
                );
                const safeUrl = issue.urlPath || '/issues/';
                return `<li>
                    <span class="mono">${issueNumber ? `#${issueNumber}` : '#00000'}</span>
                    <span class="mono archive-date">${displayDate}</span>
                    <a class="archive-headline" href="${safeUrl}">${subject}</a>
                    <span class="mono archive-tag">[issue]</span>
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
                const countText = row ? (row.textContent || '') : '';
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

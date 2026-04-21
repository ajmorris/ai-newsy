document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('subscribe-form');
    const emailInput = document.getElementById('email');
    const websiteInput = document.getElementById('website');
    const submitBtn = document.getElementById('submit-btn');
    const formMessage = document.getElementById('form-message');
    const captchaTokenInput = document.getElementById('captcha-token');
    const captchaProviderInput = document.getElementById('captcha-provider');
    const captchaContainer = document.getElementById('captcha-container');
    const hcaptchaWidget = document.getElementById('hcaptcha-widget');
    const latestIssueCallout = document.getElementById('new-issue-callout');
    const recentIssuesList = document.getElementById('recent-issues-list');
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
        showMessage('Captcha failed to load. You can still continue; anti-spam checks remain active.', 'error');
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

    // Fail-open: if no site key is configured, skip captcha on the frontend.
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
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const emailInput = form.querySelector('input[name="email"]');
            const websiteInput = form.querySelector('input[name="website"]');
            const submitButton = form.querySelector('.submit-btn');
            const formMeta = form.querySelector('.form-meta');
            const successPanel = form.querySelector('.form-success');
            const successBody = form.querySelector('.success-body');
            const subscribeRow = form.querySelector('.subscribe-row');

        if (captchaState.required && !captchaState.loadError && (!captchaState.ready || !captchaState.solved || !captchaToken)) {
            showMessage('Please complete the captcha before subscribing.', 'error');
            return;
        }

        // Show loading state
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
        formMessage.textContent = '';
        formMessage.className = 'form-message';

            const email = emailInput.value.trim();
            const honeypotValue = websiteInput ? websiteInput.value : '';
            const captchaToken = (form.querySelector('input[name="captchaToken"]') || {}).value || '';
            const captchaProvider = (form.querySelector('input[name="captchaProvider"]') || {}).value || '';

            form.classList.remove('form-error');
            form.classList.remove('form-success-state');
            formMeta.textContent = '» free · one email / day · unsub anytime';
            successPanel.hidden = true;
            subscribeRow.hidden = false;

            if (response.ok) {
                if (data.status === 'pending') {
                    showMessage('🎉 Check your email to confirm your subscription!', 'success');
                } else {
                    showMessage('🎉 You are subscribed. Welcome to AI Newsy!', 'success');
                }
                emailInput.value = '';
                if (websiteInput) {
                    websiteInput.value = '';
                }
                emailInput.value = '';
                setCaptchaToken('', captchaProvider);
                captchaState.solved = false;
                if (window.hcaptcha && typeof captchaState.widgetId === 'number') {
                    window.hcaptcha.reset(captchaState.widgetId);
                }

                // Update subscriber count animation
                updateSubscriberCount();
            } else {
                showMessage(data.error || 'Something went wrong. Please try again.', 'error');
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
            const response = await fetch('/issues/index.json', {
                headers: {
                    Accept: 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load archive manifest.');
            }

            const data = await response.json();
            renderRecentIssues(data.recentIssues || []);
        } catch (error) {
            console.error('Issue archive load error:', error);
            recentIssuesList.innerHTML = '<li class="issues-loading">No issues published yet. Check back soon.</li>';
        }
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

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

});

document.addEventListener('DOMContentLoaded', () => {
    const forms = Array.from(document.querySelectorAll('.subscribe-form'));
    const navSubscribeButton = document.getElementById('nav-subscribe-btn');
    const recentIssuesList = document.getElementById('recent-issues-list');

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
    window.onHCaptchaSuccess = (token) => setCaptchaToken(token, 'hcaptcha');
    window.onHCaptchaExpired = () => setCaptchaToken('', 'hcaptcha');

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

            if (!email) {
                applyErrorState(form, formMeta, 'Field required.');
                return;
            }
            if (!isValidEmail(email)) {
                applyErrorState(form, formMeta, 'Invalid email format.');
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
                const data = await response.json();

                if (!response.ok) {
                    applyErrorState(form, formMeta, data.error || 'Invalid email format.');
                    return;
                }

                form.classList.add('form-success-state');
                subscribeRow.hidden = true;
                successPanel.hidden = false;
                successBody.textContent = `Confirmation sent. Check your inbox. — ${email}`;
                if (websiteInput) {
                    websiteInput.value = '';
                }
                emailInput.value = '';
                setCaptchaToken('', captchaProvider);
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

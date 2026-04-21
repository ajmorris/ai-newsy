// AI Newsy - Frontend JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('subscribe-form');
    const emailInput = document.getElementById('email');
    const websiteInput = document.getElementById('website');
    const submitBtn = document.getElementById('submit-btn');
    const formMessage = document.getElementById('form-message');
    const captchaTokenInput = document.getElementById('captcha-token');
    const captchaProviderInput = document.getElementById('captcha-provider');
    const latestIssueCallout = document.getElementById('new-issue-callout');
    const recentIssuesList = document.getElementById('recent-issues-list');

    loadRecentIssues();

    function setCaptchaToken(token, provider) {
        if (captchaTokenInput) {
            captchaTokenInput.value = token || '';
        }

        if (captchaProviderInput) {
            captchaProviderInput.value = provider || '';
        }
    }

    // Expose callbacks for captcha widgets if enabled in the page.
    window.onTurnstileSuccess = (token) => setCaptchaToken(token, 'turnstile');
    window.onTurnstileExpired = () => setCaptchaToken('', 'turnstile');
    window.onHCaptchaSuccess = (token) => setCaptchaToken(token, 'hcaptcha');
    window.onHCaptchaExpired = () => setCaptchaToken('', 'hcaptcha');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = emailInput.value.trim();
        const honeypotValue = websiteInput ? websiteInput.value : '';
        const captchaToken = captchaTokenInput ? captchaTokenInput.value : '';
        const captchaProvider = captchaProviderInput ? captchaProviderInput.value : '';

        if (!email || !isValidEmail(email)) {
            showMessage('Please enter a valid email address.', 'error');
            return;
        }

        // Show loading state
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
        formMessage.textContent = '';
        formMessage.className = 'form-message';

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

            if (response.ok) {
                showMessage('🎉 Check your email to confirm your subscription!', 'success');
                emailInput.value = '';
                if (websiteInput) {
                    websiteInput.value = '';
                }
                setCaptchaToken('', captchaProvider);

                // Update subscriber count animation
                updateSubscriberCount();
            } else {
                showMessage(data.error || 'Something went wrong. Please try again.', 'error');
            }
        } catch (error) {
            console.error('Subscription error:', error);
            showMessage('Network error. Please try again.', 'error');
        } finally {
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        }
    });

    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    function showMessage(text, type) {
        formMessage.textContent = text;
        formMessage.className = `form-message ${type}`;
    }

    function updateSubscriberCount() {
        const countEl = document.querySelector('.subscriber-count');
        if (countEl) {
            const currentCount = parseInt(countEl.textContent) || 500;
            countEl.textContent = `${currentCount + 1}+`;

            // Add a little animation
            countEl.style.transform = 'scale(1.2)';
            setTimeout(() => {
                countEl.style.transform = 'scale(1)';
            }, 200);
        }
    }

    async function loadRecentIssues() {
        if (!latestIssueCallout || !recentIssuesList) {
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
            renderLatestIssue(data.latestIssue);
            renderRecentIssues(data.recentIssues || []);
        } catch (error) {
            console.error('Issue archive load error:', error);
            recentIssuesList.innerHTML = '<li class="issues-loading">No issues published yet. Check back soon.</li>';
        }
    }

    function renderLatestIssue(latestIssue) {
        if (!latestIssue || !latestIssue.urlPath) {
            return;
        }

        const titleEl = latestIssueCallout.querySelector('h3');
        const bodyEl = latestIssueCallout.querySelector('p:not(.issue-kicker)');
        const readLinkEl = latestIssueCallout.querySelector('.issue-read-link');

        if (titleEl) {
            titleEl.textContent = latestIssue.subject || 'New issue out';
        }
        if (bodyEl) {
            bodyEl.textContent = latestIssue.intro || 'Read the latest issue now, then subscribe to get tomorrow\'s edition by email.';
        }
        if (readLinkEl) {
            readLinkEl.setAttribute('href', latestIssue.urlPath);
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
                const articleCount = Number.isFinite(issue.articleCount)
                    ? `${issue.articleCount} stories`
                    : '';
                const meta = [displayDate, articleCount].filter(Boolean).join(' • ');
                const safeUrl = issue.urlPath || '/issues/';
                return `<li><a href="${safeUrl}">${subject}</a><span>${escapeHtml(meta)}</span></li>`;
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

    // Add email input focus effects
    emailInput.addEventListener('focus', () => {
        emailInput.parentElement.classList.add('focused');
    });

    emailInput.addEventListener('blur', () => {
        emailInput.parentElement.classList.remove('focused');
    });
});

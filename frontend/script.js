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
                // #region agent log
                fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'pre-fix',hypothesisId:'H1-H4',location:'frontend/script.js:74',message:'Subscribe submit started',data:{formVariant:form.dataset.formVariant || 'unknown',emailDomain:(email.split('@')[1] || '').toLowerCase(),hasCaptchaToken:Boolean(captchaToken),captchaProvider:captchaProvider || 'none',endpoint:'/api/subscribe'},timestamp:Date.now()})}).catch(()=>{});
                // #endregion
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
                // #region agent log
                fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'pre-fix',hypothesisId:'H2-H3',location:'frontend/script.js:87',message:'Subscribe response received',data:{ok:response.ok,status:response.status,contentType:response.headers.get('content-type') || 'missing'},timestamp:Date.now()})}).catch(()=>{});
                // #endregion
                const contentType = (response.headers.get('content-type') || '').toLowerCase();
                let data = null;
                let responseText = '';
                if (contentType.includes('application/json')) {
                    try {
                        data = await response.json();
                        // #region agent log
                        fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'post-fix',hypothesisId:'H2',location:'frontend/script.js:97',message:'Subscribe response JSON parsed',data:{hasErrorField:Boolean(data && data.error),statusField:data && data.status ? data.status : 'missing'},timestamp:Date.now()})}).catch(()=>{});
                        // #endregion
                    } catch (parseError) {
                        // #region agent log
                        fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'post-fix',hypothesisId:'H2',location:'frontend/script.js:101',message:'Subscribe response JSON parse failed',data:{errorName:parseError?.name || 'unknown',errorMessage:parseError?.message || 'unknown'},timestamp:Date.now()})}).catch(()=>{});
                        // #endregion
                    }
                } else {
                    responseText = await response.text();
                    // #region agent log
                    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'post-fix',hypothesisId:'H3',location:'frontend/script.js:108',message:'Subscribe response was non-JSON',data:{status:response.status,textSnippet:responseText.slice(0,120)},timestamp:Date.now()})}).catch(()=>{});
                    // #endregion
                }

                if (!response.ok) {
                    const errorMessage = (data && data.error) || responseText || `Request failed (${response.status}). Try again.`;
                    // #region agent log
                    fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'post-fix',hypothesisId:'H6',location:'frontend/script.js:117',message:'Subscribe API returned handled error',data:{status:response.status,errorMessage:errorMessage.slice(0,160)},timestamp:Date.now()})}).catch(()=>{});
                    // #endregion
                    applyErrorState(form, formMeta, errorMessage);
                    return;
                }

                form.classList.add('form-success-state');
                subscribeRow.hidden = true;
                successPanel.hidden = false;
                if (data && data.status === 'already-subscribed') {
                    successBody.textContent = `Already subscribed. You are on the AI Newsy list. — ${email}`;
                } else if (data && data.status === 'confirmed') {
                    successBody.textContent = `Subscription confirmed. Welcome to AI Newsy. — ${email}`;
                } else {
                    successBody.textContent = `Confirmation sent. Check your inbox. — ${email}`;
                }
                if (websiteInput) {
                    websiteInput.value = '';
                }
                emailInput.value = '';
                setCaptchaToken('', captchaProvider);
            } catch (error) {
                console.error('Subscription error:', error);
                // #region agent log
                fetch('http://127.0.0.1:7920/ingest/32461e49-42c8-4faf-8e25-7a8fe55277aa',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6111e0'},body:JSON.stringify({sessionId:'6111e0',runId:'post-fix',hypothesisId:'H1-H5',location:'frontend/script.js:128',message:'Subscribe request threw',data:{errorName:error?.name || 'unknown',errorMessage:error?.message || 'unknown'},timestamp:Date.now()})}).catch(()=>{});
                // #endregion
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

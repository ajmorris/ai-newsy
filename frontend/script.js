// AI Newsy - Frontend JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('subscribe-form');
    const emailInput = document.getElementById('email');
    const submitBtn = document.getElementById('submit-btn');
    const formMessage = document.getElementById('form-message');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = emailInput.value.trim();

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
                body: JSON.stringify({ email }),
            });

            const data = await response.json();

            if (response.ok) {
                showMessage('🎉 Check your email to confirm your subscription!', 'success');
                emailInput.value = '';

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

    // Add email input focus effects
    emailInput.addEventListener('focus', () => {
        emailInput.parentElement.classList.add('focused');
    });

    emailInput.addEventListener('blur', () => {
        emailInput.parentElement.classList.remove('focused');
    });

    // Feedback Modal
    const feedbackLink = document.getElementById('feedback-link');
    const feedbackModal = document.getElementById('feedback-modal');
    const modalClose = document.getElementById('modal-close');
    const feedbackForm = document.getElementById('feedback-form');
    const feedbackSubmit = document.getElementById('feedback-submit');
    const feedbackStatus = document.getElementById('feedback-message-status');

    function openModal() {
        feedbackModal.classList.add('active');
        feedbackModal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        feedbackModal.classList.remove('active');
        feedbackModal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    feedbackLink.addEventListener('click', (e) => {
        e.preventDefault();
        openModal();
    });

    modalClose.addEventListener('click', closeModal);

    feedbackModal.addEventListener('click', (e) => {
        if (e.target === feedbackModal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && feedbackModal.classList.contains('active')) {
            closeModal();
        }
    });

    feedbackForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('feedback-name').value.trim();
        const feedbackEmail = document.getElementById('feedback-email').value.trim();
        const message = document.getElementById('feedback-message').value.trim();

        if (!name || !feedbackEmail || !message) {
            showFeedbackStatus('Please fill in all fields.', 'error');
            return;
        }

        if (!isValidEmail(feedbackEmail)) {
            showFeedbackStatus('Please enter a valid email address.', 'error');
            return;
        }

        feedbackSubmit.classList.add('loading');
        feedbackSubmit.disabled = true;
        feedbackStatus.textContent = '';
        feedbackStatus.className = 'form-message';

        try {
            // Get reCAPTCHA token
            let recaptchaToken = '';
            if (typeof grecaptcha !== 'undefined') {
                recaptchaToken = await grecaptcha.execute(
                    document.querySelector('script[src*="recaptcha"]')
                        .src.split('render=')[1],
                    { action: 'feedback' }
                );
            }

            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    email: feedbackEmail,
                    message,
                    recaptchaToken,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                showFeedbackStatus('Thanks for your feedback!', 'success');
                feedbackForm.reset();
                setTimeout(closeModal, 2000);
            } else {
                showFeedbackStatus(data.error || 'Something went wrong. Please try again.', 'error');
            }
        } catch (error) {
            console.error('Feedback error:', error);
            showFeedbackStatus('Network error. Please try again.', 'error');
        } finally {
            feedbackSubmit.classList.remove('loading');
            feedbackSubmit.disabled = false;
        }
    });

    function showFeedbackStatus(text, type) {
        feedbackStatus.textContent = text;
        feedbackStatus.className = `form-message ${type}`;
    }
});

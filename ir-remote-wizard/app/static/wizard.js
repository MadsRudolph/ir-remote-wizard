/* IR Remote Wizard — JS for persistence, animations, and interactive features */

const STORAGE_KEY = 'ir_wizard_session';

document.addEventListener('DOMContentLoaded', function () {
    // 1. Progress Persistence
    initPersistence();

    // 2. Loading States
    initLoadingStates();

    // 3. Pulse Wave Animation (if element exists)
    initPulseWave();

    // 4. Clipboard Functionality (if element exists)
    initClipboard();
});

function initPersistence() {
    const mainForm = document.querySelector('form[action*="/connect"], form[action*="/device-type"], form[action*="/brand"]');
    if (!mainForm) return;

    // Save inputs to localStorage on change
    mainForm.querySelectorAll('input').forEach(input => {
        const savedValue = localStorage.getItem(`${STORAGE_KEY}_${input.name}`);
        if (savedValue && !input.value) {
            input.value = savedValue;
        }

        input.addEventListener('input', () => {
            localStorage.setItem(`${STORAGE_KEY}_${input.name}`, input.value);
        });
    });

    // Clear persistence on completion (results page)
    if (window.location.pathname.includes('/results')) {
        localStorage.clear();
    }
}

function initLoadingStates() {
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.classList.contains('btn-danger')) {
                btn.classList.add('btn-loading');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner"></span> Processing...';
            }
        });
    });
}

function initPulseWave() {
    const pulseContainer = document.querySelector('.pulse-container');
    if (pulseContainer) {
        // Toggle active class when "Send" is pressed
        const sendBtn = document.querySelector('form[action*="/send-test"] button');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                pulseContainer.classList.add('pulse-active');
                setTimeout(() => pulseContainer.classList.remove('pulse-active'), 2000);
            });
        }
    }
}

function initClipboard() {
    const copyBtn = document.getElementById('copy-yaml');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const yaml = document.querySelector('.yaml-preview code').innerText;
            navigator.clipboard.writeText(yaml).then(() => {
                const originalText = copyBtn.innerText;
                copyBtn.innerText = '✅ Copied!';
                copyBtn.classList.replace('btn-primary', 'btn-success');
                setTimeout(() => {
                    copyBtn.innerText = originalText;
                    copyBtn.classList.replace('btn-success', 'btn-primary');
                }, 2000);
            });
        });
    }
}

// Bulk Blast Logic (called from UI)
window.startBulkBlast = async function (session_id) {
    const btn = document.getElementById('bulk-blast-btn');
    const status = document.getElementById('bulk-status');
    const pulseContainer = document.querySelector('.pulse-container');

    if (!btn) return;

    btn.disabled = true;
    btn.innerText = '🚀 Blasting...';
    if (status) status.innerText = 'Sending sequence of power codes...';
    if (pulseContainer) pulseContainer.classList.add('pulse-active');

    try {
        const formData = new FormData();
        formData.append('session_id', session_id);

        const response = await fetch('/bulk-blast', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            btn.innerText = '✅ Sequence Done';
            if (status) status.innerText = 'Sequence complete. Did the device turn on?';

            // Show confirmation UI by simulating a "sent" state if needed
            // For now, let's just show the buttons if they were hidden
            const confirmSection = document.querySelector('.confirm-section');
            if (confirmSection) {
                confirmSection.style.display = 'block';
                confirmSection.style.animation = 'fadeInUp 0.4s ease-out';
            }
        } else {
            btn.innerText = '❌ Failed';
            if (status) status.innerText = 'Blast failed. Check connection.';
        }
    } catch (e) {
        console.error(e);
        btn.innerText = '❌ Error';
    } finally {
        setTimeout(() => {
            if (pulseContainer) pulseContainer.classList.remove('pulse-active');
            btn.disabled = false;
            btn.innerText = 'Bulk Blast (Try All)';
        }, 3000);
    }
};

// Quick Save for chips
window.quickSave = function (name) {
    const input = document.getElementById('btn_name');
    const form = document.querySelector('.learn-save-form');
    if (input && form) {
        input.value = name;
        form.submit();
    }
};

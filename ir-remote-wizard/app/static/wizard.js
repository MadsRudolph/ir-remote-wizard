/* IR Remote Wizard — JS for particles, animations, and interactive features */

const STORAGE_KEY = 'ir_wizard_session';

document.addEventListener('DOMContentLoaded', function () {
    initParticles();
    initPersistence();
    initLoadingStates();
    initClipboard();
    initPageTransitions();
});

/* ─── Particle Background ─── */
function initParticles() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    const PARTICLE_COUNT = 45;
    const CONNECTION_DISTANCE = 120;
    let animId;
    let w, h;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    function createParticle() {
        return {
            x: Math.random() * w,
            y: Math.random() * h,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            r: Math.random() * 1.5 + 0.5,
            alpha: Math.random() * 0.4 + 0.1,
        };
    }

    function init() {
        resize();
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push(createParticle());
        }
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);

        // Draw connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < CONNECTION_DISTANCE) {
                    const opacity = (1 - dist / CONNECTION_DISTANCE) * 0.15;
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(99, 102, 241, ${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw particles
        for (const p of particles) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(165, 180, 252, ${p.alpha})`;
            ctx.fill();
        }
    }

    function update() {
        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0 || p.x > w) p.vx *= -1;
            if (p.y < 0 || p.y > h) p.vy *= -1;
        }
    }

    function loop() {
        update();
        draw();
        animId = requestAnimationFrame(loop);
    }

    // Only run particles if user hasn't set prefers-reduced-motion
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        init();
        loop();
        window.addEventListener('resize', () => {
            resize();
        });
    }
}

/* ─── Persistence ─── */
function initPersistence() {
    const mainForm = document.querySelector('form[action*="/connect"], form[action*="/device-type"], form[action*="/brand"]');
    if (!mainForm) return;

    mainForm.querySelectorAll('input').forEach(input => {
        const savedValue = localStorage.getItem(`${STORAGE_KEY}_${input.name}`);
        if (savedValue && !input.value) {
            input.value = savedValue;
        }

        input.addEventListener('input', () => {
            localStorage.setItem(`${STORAGE_KEY}_${input.name}`, input.value);
        });
    });

    if (window.location.pathname.includes('/results')) {
        localStorage.clear();
    }
}

/* ─── Loading States ─── */
function initLoadingStates() {
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.classList.contains('btn-danger') && !btn.classList.contains('btn-loading')) {
                btn.classList.add('btn-loading');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner"></span> Processing...';
            }
        });
    });
}



/* ─── Clipboard ─── */
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

/* ─── Page Transitions ─── */
function initPageTransitions() {
    document.querySelectorAll('a[href]:not([target="_blank"]):not([href^="#"])').forEach(link => {
        link.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (!href || href.startsWith('javascript:')) return;

            e.preventDefault();
            document.getElementById('main-content').classList.add('page-leaving');
            setTimeout(() => {
                window.location.href = href;
            }, 180);
        });
    });
}

/* ─── Bulk Blast Logic ─── */
window.startBulkBlast = async function (session_id) {
    const btn = document.getElementById('bulk-blast-btn');
    const status = document.getElementById('bulk-status');


    if (!btn) return;

    btn.disabled = true;
    btn.innerText = '🚀 Blasting...';


    try {
        const formData = new FormData();
        formData.append('session_id', session_id);

        const url = btn.dataset.url || '/bulk-blast';
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            btn.innerText = '✅ Sequence Done';
            if (status) status.innerText = 'Sequence complete. Did the device respond?';

            const bulkConfirm = document.getElementById('bulk-confirm-section');
            if (bulkConfirm) {
                bulkConfirm.style.display = 'block';
                bulkConfirm.style.animation = 'fadeInUp 0.4s ease-out';
            }
        } else {
            btn.innerText = '❌ Failed';
            if (status) status.innerText = 'Blast failed. Check connection.';
        }
    } catch (e) {
        console.error(e);
        btn.innerText = '❌ Error';
    }
};

/* ─── Quick Save (for learn mode chips) ─── */
window.quickSave = function (name) {
    const input = document.getElementById('btn_name');
    const form = document.querySelector('.learn-save-form');
    if (input && form) {
        input.value = name;
        form.submit();
    }
};

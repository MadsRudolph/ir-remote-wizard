/* IR Remote Wizard — minimal JS for interactive features */

document.addEventListener('DOMContentLoaded', function () {
    // Add loading state to forms on submit
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.classList.contains('btn-danger')) {
                btn.disabled = true;
                btn.style.opacity = '0.7';
            }
        });
    });
});

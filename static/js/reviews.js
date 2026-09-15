/* ============================================================
   QUICKBITE — REVIEW INTERACTIONS (Phase 9)
   Helpful toggle + report button (delegated, AJAX, CSRF)
   ============================================================ */

(function () {
    'use strict';

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
    }

    async function post(url) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            return await res.json();
        } catch (e) {
            return { ok: false, message: 'Network error — please try again.' };
        }
    }

    document.addEventListener('click', async (e) => {
        const helpful = e.target.closest('[data-helpful-id]');
        if (helpful) {
            const data = await post('/reviews/' + helpful.dataset.helpfulId + '/helpful/');
            if (!data.ok) {
                if (typeof showToast === 'function') showToast(data.message || 'Please log in first.');
                return;
            }
            helpful.classList.toggle('active', data.active);
            helpful.querySelector('.count').textContent = data.helpful_count;
            return;
        }

        const report = e.target.closest('[data-report-id]');
        if (report) {
            if (!confirm('Report this review to the QuickBite team?')) return;
            const data = await post('/reviews/' + report.dataset.reportId + '/report/');
            if (data.ok && typeof showToast === 'function') showToast(data.message);
            report.disabled = true;
            report.innerHTML = '<i class="bx bx-check"></i> Reported';
        }
    });
})();

/* ============================================================
   QUICKBITE — DELIVERY LOCATION (Phase 9)
   Browser geolocation + city presets · stored in the session
   ============================================================ */

(function () {
    'use strict';

    const menu = document.getElementById('locationMenu');
    if (!menu) return;
    const btn = document.getElementById('locationBtn');
    const popup = document.getElementById('locationPopup');
    const status = document.getElementById('locStatus');
    const labelEl = document.getElementById('locationLabel');

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
    }

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) menu.classList.remove('open');
    });

    async function setLocation(payload) {
        status.textContent = 'Saving…';
        try {
            const res = await fetch('/location/set/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.message || 'Could not save location');
            labelEl.textContent = data.label;
            status.textContent = '';
            if (typeof showToast === 'function') showToast(data.message);
            menu.classList.remove('open');
            // distances/ETAs across the page are server-rendered — refresh once
            setTimeout(() => window.location.reload(), 900);
        } catch (err) {
            status.textContent = err.message || 'Something went wrong.';
        }
    }

    document.getElementById('useMyLocation').addEventListener('click', () => {
        if (!navigator.geolocation) {
            status.textContent = 'Geolocation is not supported by this browser.';
            return;
        }
        status.textContent = 'Finding you…';
        navigator.geolocation.getCurrentPosition(
            (pos) => setLocation({
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                label: 'Current Location',
            }),
            () => { status.textContent = 'Location permission denied — pick a city instead.'; },
            { timeout: 8000 },
        );
    });

    popup.querySelectorAll('[data-city]').forEach((b) => {
        b.addEventListener('click', () => setLocation({ city: b.dataset.city }));
    });
})();

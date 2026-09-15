/* ============================================================
   QUICKBITE — AJAX FILTERS (Phase 9)
   Works on both /menu/ (#menuFilters → #menuResults) and
   /restaurants/ (#restFilters → #restResults). No page reloads:
   fetches ?ajax=1 partials, swaps HTML, rewrites the URL.
   ============================================================ */

(function () {
    'use strict';

    const setup = document.getElementById('menuFilters')
        ? { form: 'menuFilters', results: 'menuResults' }
        : document.getElementById('restFilters')
            ? { form: 'restFilters', results: 'restResults' }
            : null;
    if (!setup) return;

    const form = document.getElementById(setup.form);
    const results = document.getElementById(setup.results);
    let inFlight = null;

    // ---------- build querystring from the form ----------
    function params() {
        const data = new FormData(form);
        const usp = new URLSearchParams();
        const cuisines = data.getAll('cuisines').filter(Boolean);
        for (const [key, value] of data.entries()) {
            if (key === 'cuisines') continue;
            if (value !== '') usp.set(key, value);
        }
        if (cuisines.length) usp.set('cuisines', cuisines.join(','));
        // normalise the price slider pair
        const min = usp.get('min_price');
        const max = usp.get('max_price');
        if (min && max && +min > +max) { usp.set('min_price', max); usp.set('max_price', min); }
        if (min === '0') usp.delete('min_price');
        if (max === '600') usp.delete('max_price');
        return usp;
    }

    async function apply(replaceUrl = true) {
        const usp = params();
        const controller = new AbortController();
        if (inFlight) inFlight.abort();
        inFlight = controller;
        results.classList.add('qb-results-loading');
        try {
            const res = await fetch(window.location.pathname + '?ajax=1&' + usp.toString(),
                                    { signal: controller.signal });
            results.innerHTML = await res.text();
            if (replaceUrl) {
                window.history.replaceState({}, '', '?' + usp.toString());
            }
            if (window.AOS) window.AOS.refreshHard();
        } catch (e) {
            if (e.name !== 'AbortError') console.error('filter fetch failed', e);
        } finally {
            results.classList.remove('qb-results-loading');
            inFlight = null;
        }
    }

    // ---------- debounce helper ----------
    let timer = null;
    function debouncedApply(ms) {
        clearTimeout(timer);
        timer = setTimeout(() => apply(), ms);
    }

    // ---------- events ----------
    form.addEventListener('change', (e) => {
        if (e.target.matches('input[type="text"]')) return;  // handled by input event
        apply();
    });
    form.addEventListener('input', (e) => {
        if (e.target.matches('input[type="text"]')) {
            debouncedApply(+(e.target.dataset.debounce || 400));
        }
    });
    // suppress native GET submit (no-JS fallback still works)
    form.addEventListener('submit', (e) => { e.preventDefault(); apply(); });

    // ---------- dual price slider ----------
    const slider = document.getElementById('priceSlider');
    if (slider) {
        const [minR, maxR] = slider.querySelectorAll('input[type="range"]');
        const minL = document.getElementById('priceMinLabel');
        const maxL = document.getElementById('priceMaxLabel');
        const fill = slider.querySelector('.qb-range-fill');
        const MAX = +maxR.max;

        function paint() {
            let lo = +minR.value, hi = +maxR.value;
            if (lo > hi) { [lo, hi] = [hi, lo]; }
            minL.textContent = '₹' + lo;
            maxL.textContent = '₹' + hi + (hi >= MAX ? '+' : '');
            fill.style.left = (lo / MAX * 100) + '%';
            fill.style.right = (100 - hi / MAX * 100) + '%';
        }
        [minR, maxR].forEach(r => {
            r.addEventListener('input', paint);
            r.addEventListener('change', () => apply());
        });
        paint();
    }

    // ---------- category sidebar (menu page) ----------
    document.querySelectorAll('[data-category]').forEach((a) => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('[data-category]').forEach(x => x.classList.remove('active'));
            a.classList.add('active');
            form.elements.category.value = a.dataset.category;
            apply();
        });
    });

    // ---------- clear all ----------
    const clearBtn = document.getElementById('clearFilters');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            form.reset();
            if (form.elements.category) form.elements.category.value = '';
            document.querySelectorAll('[data-category]').forEach(x => x.classList.remove('active'));
            const all = document.querySelector('[data-category=""]');
            if (all) all.classList.add('active');
            if (slider) {
                const [minR, maxR] = slider.querySelectorAll('input[type="range"]');
                minR.value = minR.min; maxR.value = maxR.max;
                minR.dispatchEvent(new Event('input'));
            }
            apply();
        });
    }

    // ---------- delegated: active tags + pagination stay AJAX ----------
    results.addEventListener('click', (e) => {
        const link = e.target.closest('a.qb-tag, a.page-btn');
        if (!link) return;
        e.preventDefault();
        fetchPartial(link.getAttribute('href'));
    });

    async function fetchPartial(href) {
        const sep = href.includes('?') ? '&' : '?';
        results.classList.add('qb-results-loading');
        try {
            const res = await fetch(href + sep + 'ajax=1');
            results.innerHTML = await res.text();
            window.history.replaceState({}, '', href);
            if (window.AOS) window.AOS.refreshHard();
            window.scrollTo({ top: results.offsetTop - 90, behavior: 'smooth' });
        } finally {
            results.classList.remove('qb-results-loading');
        }
    }
})();

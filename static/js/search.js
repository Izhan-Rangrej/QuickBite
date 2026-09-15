/* ============================================================
   QUICKBITE — GLOBAL SEARCH AUTOCOMPLETE (Phase 9)
   Debounced fetch to /search/suggest/ · keyboard nav · no deps
   ============================================================ */

(function () {
    'use strict';

    const wrap = document.getElementById('searchAc');
    if (!wrap) return;
    const input = document.getElementById('globalSearch');
    const box = document.getElementById('suggestBox');

    let timer = null;
    let activeIdx = -1;
    let items = [];

    const TYPE_ICON = { dish: 'bx-dish', restaurant: 'bx-store-alt', category: 'bx-category' };
    const TYPE_LABEL = { dish: 'Dish', restaurant: 'Restaurant', category: 'Category' };

    function close() {
        box.hidden = true;
        box.innerHTML = '';
        activeIdx = -1;
        items = [];
    }

    function render(data) {
        items = data.results || [];
        if (!items.length) {
            box.innerHTML =
                '<div class="qb-suggest-empty">No matches for “' + escapeHtml(data.q) + '”</div>' +
                '<a class="qb-suggest-all" href="/search/?q=' + encodeURIComponent(data.q) + '">' +
                'See full search <i class="bx bx-right-arrow-alt"></i></a>';
        } else {
            box.innerHTML = items.map((r, i) =>
                '<a class="qb-suggest-item" href="' + r.url + '" data-idx="' + i + '">' +
                    (r.image
                        ? '<img src="' + r.image + '" alt="" loading="lazy">'
                        : '<span class="qb-suggest-icon"><i class="bx ' + TYPE_ICON[r.type] + '"></i></span>') +
                    '<span class="qb-suggest-text">' +
                        '<strong>' + escapeHtml(r.name) + '</strong>' +
                        '<small>' + escapeHtml(r.sub) + '</small>' +
                    '</span>' +
                    '<span class="qb-suggest-right">' +
                        (r.price ? '<b>' + r.price + '</b>' : '') +
                        '<span class="qb-suggest-type">' + TYPE_LABEL[r.type] + '</span>' +
                    '</span>' +
                '</a>').join('') +
                '<a class="qb-suggest-all" href="/search/?q=' + encodeURIComponent(data.q) + '">' +
                'See all results <i class="bx bx-right-arrow-alt"></i></a>';
        }
        box.hidden = false;
        activeIdx = -1;
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[c]);
    }

    async function suggest(q) {
        try {
            const res = await fetch('/search/suggest/?q=' + encodeURIComponent(q));
            const data = await res.json();
            if (data.q === input.value.trim()) render(data);
        } catch (e) { /* stay silent */ }
    }

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (q.length < 2) { close(); return; }
        timer = setTimeout(() => suggest(q), 250);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2 && !box.hidden === false) suggest(input.value.trim());
    });

    input.addEventListener('keydown', (e) => {
        const links = box.querySelectorAll('.qb-suggest-item');
        if (!links.length) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            activeIdx = (activeIdx + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
            links.forEach(l => l.classList.remove('active'));
            links[activeIdx].classList.add('active');
            links[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter' && activeIdx >= 0) {
            e.preventDefault();
            window.location = links[activeIdx].href;
        } else if (e.key === 'Escape') {
            close();
        }
    });

    document.addEventListener('click', (e) => {
        if (!wrap.contains(e.target)) close();
    });
})();

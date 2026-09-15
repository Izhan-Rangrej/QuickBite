/* ============================================================
   QUICKBITE — CART & WISHLIST AJAX (Phase 7)
   Fetch API + CSRF · delegated events (survive AJAX HTML swaps)
   Reuses showToast(), cartBounce/fadeInUp keyframes from script.js
   ============================================================ */

(function () {
    'use strict';

    // ---------- CSRF ----------
    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
    }

    // ---------- JSON POST helper ----------
    async function post(url, data, busyEl) {
        if (busyEl) busyEl.classList.add('qb-loading');
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify(data || {}),
            });
            return await res.json();
        } catch (err) {
            return { ok: false, message: 'Network error — please try again. 😕' };
        } finally {
            if (busyEl) busyEl.classList.remove('qb-loading');
        }
    }

    // ---------- UI refresh from an AJAX bundle ----------
    function applyBundle(data) {
        // 1) badge
        const badge = document.getElementById('cartCount');
        if (badge && typeof data.cart_count === 'number') {
            badge.textContent = data.cart_count;
            badge.classList.toggle('qb-hidden', data.cart_count === 0);
        }

        // 2) sidebar (swap .cart-items and .cart-footer in place)
        if (data.sidebar_html) {
            const frag = document.createElement('div');
            frag.innerHTML = data.sidebar_html;
            const newItems = frag.querySelector('.cart-items');
            const newFooter = frag.querySelector('.cart-footer');
            const oldItems = document.querySelector('#cartSidebar .cart-items');
            const oldFooter = document.querySelector('#cartSidebar .cart-footer');
            if (newItems && oldItems) oldItems.replaceWith(newItems);
            if (newFooter && oldFooter) oldFooter.replaceWith(newFooter);
        }

        // 3) cart page surfaces
        if (data.lines_html) {
            const oldLines = document.getElementById('cartLines');
            if (oldLines) {
                const frag = document.createElement('div');
                frag.innerHTML = data.lines_html;
                const newLines = frag.querySelector('#cartLines');
                if (newLines) oldLines.replaceWith(newLines);
            }
        }
        if (data.summary_html) {
            const oldSummary = document.getElementById('orderSummary');
            if (oldSummary) {
                const frag = document.createElement('div');
                frag.innerHTML = data.summary_html;
                const newSummary = frag.querySelector('#orderSummary');
                if (newSummary) oldSummary.replaceWith(newSummary);
            }
        }
    }

    function toast(data) {
        if (data && data.message && typeof showToast === 'function') {
            showToast(data.message);
        }
    }

    // ---------- cart icon bounce (same animation as the original demo) ----------
    function bounceCartIcon() {
        const cartIcon = document.getElementById('cartIcon');
        if (!cartIcon) return;
        cartIcon.style.animation = 'none';
        cartIcon.offsetHeight; // reflow
        cartIcon.style.animation = 'cartBounce 0.5s ease';
    }

    // ---------- ADD TO CART ----------
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.add-to-cart-btn[data-dish-id]');
        if (!btn) return;
        e.preventDefault();

        // dish detail page: honour the quantity selector
        const qtyInput = document.getElementById('qtyInput');
        const qty = qtyInput ? Math.max(1, parseInt(qtyInput.value, 10) || 1) : 1;

        const data = await post('/cart/add/', { dish_id: btn.dataset.dishId, quantity: qty }, btn);

        if (data.ok) {
            // original template's green "ADDED" button animation
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="bx bx-check"></i> ADDED';
            btn.style.background = '#4CAF50';
            btn.style.color = 'white';
            btn.style.borderColor = '#4CAF50';
            setTimeout(function () {
                btn.innerHTML = original;
                btn.style.background = '';
                btn.style.color = '';
                btn.style.borderColor = '';
            }, 2000);

            bounceCartIcon();
            applyBundle(data);
        }
        toast(data);
    });

    // ---------- QUANTITY +/- (sidebar + cart page) ----------
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.qty-btn[data-dish-id]');
        if (!btn) return;
        e.preventDefault();

        const qtyWrap = btn.closest('.cart-item-qty');
        const current = parseInt(qtyWrap.querySelector('span').textContent, 10) || 1;
        const next = btn.dataset.action === 'inc' ? current + 1 : current - 1;

        const data = await post('/cart/update/', { dish_id: btn.dataset.dishId, quantity: next }, btn);
        if (data.ok) applyBundle(data);
        toast(data);
    });

    // ---------- REMOVE ----------
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.qb-remove-btn[data-dish-id]');
        if (!btn) return;
        e.preventDefault();
        const data = await post('/cart/remove/', { dish_id: btn.dataset.dishId }, btn);
        if (data.ok) applyBundle(data);
        toast(data);
    });

    // ---------- COUPON ----------
    document.addEventListener('click', async function (e) {
        if (e.target.closest('#couponApplyBtn')) {
            const input = document.getElementById('couponInput');
            const data = await post('/cart/coupon/apply/', { code: input ? input.value : '' }, e.target.closest('#couponApplyBtn'));
            applyBundle(data);   // bundle is returned even on ok:false (shows error inside summary)
            toast(data);
        }
        if (e.target.closest('#couponRemoveBtn')) {
            const data = await post('/cart/coupon/remove/', {}, e.target.closest('#couponRemoveBtn'));
            if (data.ok) applyBundle(data);
            toast(data);
        }
        if (e.target.closest('#checkoutBtn')) {
            const btn = e.target.closest('#checkoutBtn');
            if (!btn.disabled) window.location.href = '/checkout/';
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.target.id === 'couponInput') {
            const btn = document.getElementById('couponApplyBtn');
            if (btn) btn.click();
        }
    });

    // ---------- WISHLIST TOGGLE ----------
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.wishlist-btn[data-dish-id]');
        if (!btn) return;
        e.preventDefault();

        const data = await post('/wishlist/toggle/', { dish_id: btn.dataset.dishId }, btn);
        if (data.ok) {
            btn.classList.toggle('active', data.wishlisted);
            btn.innerHTML = data.wishlisted
                ? '<i class="bx bxs-heart"></i>'
                : '<i class="bx bx-heart"></i>';
            // on the wishlist page, removing an item fades its card away
            if (!data.wishlisted && document.getElementById('isWishlistPage')) {
                const card = btn.closest('.dish-card');
                if (card) {
                    card.style.transition = 'opacity .4s ease, transform .4s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(.92)';
                    setTimeout(function () { card.remove(); }, 400);
                }
            }
        }
        toast(data);
    });

    // ---------- MOVE TO CART (wishlist page) ----------
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.qb-move-btn[data-dish-id]');
        if (!btn) return;
        e.preventDefault();

        const add = await post('/cart/add/', { dish_id: btn.dataset.dishId, quantity: 1 }, btn);
        if (!add.ok) { toast(add); return; }

        applyBundle(add);
        bounceCartIcon();
        toast(add);

        // un-wishlist it so it "moves"
        const removed = await post('/wishlist/toggle/', { dish_id: btn.dataset.dishId });
        if (removed.ok) {
            const card = btn.closest('.dish-card');
            if (card) {
                card.style.transition = 'opacity .4s ease, transform .4s ease';
                card.style.opacity = '0';
                card.style.transform = 'scale(.92)';
                setTimeout(function () { card.remove(); }, 400);
            }
        }
    });
})();

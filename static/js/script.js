// ============================================
// QUICKBITE - COMPLETE JAVASCRIPT
// ============================================

// ========== PRELOADER ==========
window.addEventListener('load', () => {
    const preloader = document.getElementById('preloader');
    setTimeout(() => {
        preloader.classList.add('hidden');
    }, 1500);
});

// ========== INITIALIZE AOS ==========
AOS.init({
    duration: 800,
    easing: 'ease-in-out',
    once: true,
    offset: 100,
    disable: 'mobile'
});

// ========== NAVBAR SCROLL EFFECT ==========
const navbar = document.getElementById('navbar');
const backToTop = document.getElementById('backToTop');

window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;

    // Navbar background
    if (scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }

    // Back to top button
    if (scrollY > 500) {
        backToTop.classList.add('visible');
    } else {
        backToTop.classList.remove('visible');
    }

    // Active nav link
    updateActiveNavLink();
});

// ========== BACK TO TOP ==========
backToTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ========== ACTIVE NAV LINK ON SCROLL ==========
function updateActiveNavLink() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-links a');
    
    let current = '';
    sections.forEach(section => {
        const sectionTop = section.offsetTop - 100;
        if (window.scrollY >= sectionTop) {
            current = section.getAttribute('id');
        }
    });

    navLinks.forEach(link => {
        link.classList.remove('active');
        // endsWith so both "#home" and "/#home" (Django {% url %} anchors) match
        if (link.getAttribute('href').endsWith(`#${current}`)) {
            link.classList.add('active');
        }
    });
}

// ========== MOBILE MENU ==========
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('navLinks');

hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    navLinks.classList.toggle('active');
});

// Close mobile menu on link click
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => {
        hamburger.classList.remove('active');
        navLinks.classList.remove('active');
    });
});

// ========== CART SIDEBAR ==========
const cartIcon = document.getElementById('cartIcon');
const cartSidebar = document.getElementById('cartSidebar');
const closeCart = document.getElementById('closeCart');
const cartOverlay = document.getElementById('cartOverlay');

cartIcon.addEventListener('click', () => {
    cartSidebar.classList.add('active');
    cartOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
});

function closeCartSidebar() {
    cartSidebar.classList.remove('active');
    cartOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

closeCart.addEventListener('click', closeCartSidebar);
cartOverlay.addEventListener('click', closeCartSidebar);

// ========== FILTER TABS ==========
const filterBtns = document.querySelectorAll('.filter-btn');
const dishCards = document.querySelectorAll('.dish-card');

filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // Remove active class from all buttons
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;

        dishCards.forEach(card => {
            if (filter === 'all' || card.dataset.category === filter) {
                card.classList.remove('hidden');
                card.style.animation = 'fadeInUp 0.5s ease forwards';
            } else {
                card.classList.add('hidden');
            }
        });
    });
});

// ========== ADD TO CART ==========
// Real add-to-cart logic (AJAX) lives in cart.js — it reuses the cartBounce
// keyframes injected below and the showToast() helper.

// Cart bounce animation
const style = document.createElement('style');
style.textContent = `
    @keyframes cartBounce {
        0%, 100% { transform: scale(1); }
        25% { transform: scale(1.3); }
        50% { transform: scale(0.9); }
        75% { transform: scale(1.1); }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);

// ========== WISHLIST TOGGLE ==========
// Real wishlist logic (AJAX + persisted to the account) lives in cart.js —
// it keeps the same heart-fill animation and toasts.

// ========== TOAST NOTIFICATION ==========
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toastMessage');

function showToast(message) {
    toastMessage.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ========== COPY COUPON CODE ==========
function copyCode(code) {
    navigator.clipboard.writeText(code).then(() => {
        showToast(`Coupon "${code}" copied! 📋`);
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = code;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showToast(`Coupon "${code}" copied! 📋`);
    });
}

// ========== QUANTITY BUTTONS ==========
const qtyBtns = document.querySelectorAll('.qty-btn');

qtyBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const qtySpan = btn.parentElement.querySelector('span');
        let qty = parseInt(qtySpan.textContent);

        if (btn.textContent === '+') {
            qty++;
        } else if (btn.textContent === '-' && qty > 1) {
            qty--;
        }

        qtySpan.textContent = qty;
    });
});

// ========== SMOOTH SCROLL FOR NAV LINKS ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// ========== COUNTER ANIMATION ==========
function animateCounters() {
    const counters = document.querySelectorAll('.stat-item h3');
    
    counters.forEach(counter => {
        const target = counter.textContent;
        const numericTarget = parseInt(target.replace(/[^0-9]/g, ''));
        const suffix = target.replace(/[0-9]/g, '');
        let current = 0;
        const increment = numericTarget / 60;
        const timer = setInterval(() => {
            current += increment;
            if (current >= numericTarget) {
                counter.textContent = target;
                clearInterval(timer);
            } else {
                counter.textContent = Math.ceil(current) + suffix;
            }
        }, 30);
    });
}

// Trigger counter animation when hero section is visible
const heroSection = document.getElementById('home');
const heroObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            setTimeout(animateCounters, 500);
            heroObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.5 });

heroObserver.observe(heroSection);

// ========== SEARCH BOX FUNCTIONALITY ==========
const searchInput = document.querySelector('.search-box input');
if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        
        dishCards.forEach(card => {
            const title = card.querySelector('h3').textContent.toLowerCase();
            const restaurant = card.querySelector('.dish-restaurant').textContent.toLowerCase();
            
            if (title.includes(query) || restaurant.includes(query) || query === '') {
                card.classList.remove('hidden');
            } else {
                card.classList.add('hidden');
            }
        });
    });
}

// ========== PARALLAX EFFECT ON HERO ==========
window.addEventListener('mousemove', (e) => {
    const heroImage = document.querySelector('.main-hero-img');
    if (!heroImage) return;

    const xAxis = (window.innerWidth / 2 - e.pageX) / 50;
    const yAxis = (window.innerHeight / 2 - e.pageY) / 50;

    heroImage.style.transform = `translateY(${Math.sin(Date.now() / 1000) * 20}px) rotateY(${xAxis}deg) rotateX(${yAxis}deg)`;
});

// ========== NEWSLETTER FORM ==========
const newsletterForm = document.querySelector('.newsletter-form');
if (newsletterForm) {
    newsletterForm.addEventListener('submit', (e) => {
        e.preventDefault();
    });
    
    const subscribeBtn = newsletterForm.querySelector('.btn');
    subscribeBtn.addEventListener('click', () => {
        const emailInput = newsletterForm.querySelector('input');
        if (emailInput.value && emailInput.value.includes('@')) {
            showToast('Subscribed successfully! 🎉');
            emailInput.value = '';
        } else {
            showToast('Please enter a valid email 📧');
        }
    });
}

// ========== CATEGORY CARD HOVER EFFECT ==========
const categoryCards = document.querySelectorAll('.category-card');
categoryCards.forEach(card => {
    card.addEventListener('click', () => {
        const categoryName = card.querySelector('h4').textContent.trim().toLowerCase().replace(/\s+/g, '-');
        
        // Scroll to popular section
        document.getElementById('popular').scrollIntoView({ behavior: 'smooth' });
        
        // Activate corresponding filter
        setTimeout(() => {
            const matchingFilter = document.querySelector(`.filter-btn[data-filter="${categoryName}"]`);
            if (matchingFilter) {
                matchingFilter.click();
            }
        }, 800);
    });
});

// ========== PAGE LOAD ANIMATION ==========
document.addEventListener('DOMContentLoaded', () => {
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 100);
});

console.log('🍔 QuickBite loaded successfully!');
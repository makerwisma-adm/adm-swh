/**
 * SPPG Wisma Haji - Animation JavaScript
 * Handles scroll animations, counters, and interactive effects
 */

document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  // ============================================
  // SCROLL ANIMATIONS (Intersection Observer)
  // ============================================

  const scrollAnimatedElements = document.querySelectorAll('.scroll-animate, .card-animated, .kpi-card-animated');

  if (scrollAnimatedElements.length > 0) {
    const scrollObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });

    scrollAnimatedElements.forEach(el => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(30px)';
      scrollObserver.observe(el);
    });
  }

  // ============================================
  // NUMBER COUNTER ANIMATION
  // ============================================

  function animateCounter(element, target, duration = 2000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        element.textContent = formatRupiah(target);
        clearInterval(timer);
      } else {
        element.textContent = formatRupiah(Math.floor(current));
      }
    }, 16);
  }

  function formatRupiah(number) {
    return new Intl.NumberFormat('id-ID').format(number);
  }

  const counters = document.querySelectorAll('[data-counter]');
  if (counters.length > 0) {
    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.classList.contains('counted')) {
          entry.target.classList.add('counted');
          const target = parseInt(entry.target.dataset.counter, 10);
          animateCounter(entry.target, target);
        }
      });
    }, { threshold: 0.5 });

    counters.forEach(counter => {
      counterObserver.observe(counter);
    });
  }

  // ============================================
  // STAGGERED ANIMATION FOR LISTS
  // ============================================

  function staggerAnimate(selector, delayBase = 100) {
    const items = document.querySelectorAll(selector);
    items.forEach((item, index) => {
      item.style.animationDelay = `${index * delayBase}ms`;
      item.classList.add('animate-fade-in-up');
    });
  }

  // Apply to tables
  staggerAnimate('.table-animated tbody tr', 50);

  // Apply to cards
  staggerAnimate('.grid-cards .card-animated', 100);

  // ============================================
  // BUTTON RIPPLE EFFECT
  // ============================================

  document.querySelectorAll('.btn-ripple').forEach(button => {
    button.addEventListener('click', function(e) {
      const rect = button.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const ripple = document.createElement('span');
      ripple.className = 'ripple';
      ripple.style.left = x + 'px';
      ripple.style.top = y + 'px';

      button.appendChild(ripple);

      setTimeout(() => ripple.remove(), 600);
    });
  });

  // ============================================
  // SMOOTH SCROLL TO TOP
  // ============================================

  const scrollTopBtn = document.querySelector('.scroll-top');
  if (scrollTopBtn) {
    window.addEventListener('scroll', () => {
      if (window.pageYOffset > 300) {
        scrollTopBtn.classList.add('visible');
      } else {
        scrollTopBtn.classList.remove('visible');
      }
    });

    scrollTopBtn.addEventListener('click', () => {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    });
  }

  // ============================================
  // SIDEBAR TOGGLE ANIMATION
  // ============================================

  const sidebarToggle = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      sidebarToggle.classList.toggle('active');

      // Save state
      localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });

    // Restore state
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
      sidebar.classList.add('collapsed');
      sidebarToggle.classList.add('active');
    }
  }

  // ============================================
  // TABS ANIMATION
  // ============================================

  document.querySelectorAll('.tab-animated').forEach(tab => {
    tab.addEventListener('click', function() {
      const tabGroup = this.closest('.tabs-container');
      const targetId = this.dataset.tab;

      // Remove active class from all tabs
      tabGroup.querySelectorAll('.tab-animated').forEach(t => t.classList.remove('active'));

      // Add active class to clicked tab
      this.classList.add('active');

      // Hide all tab contents
      tabGroup.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
      });

      // Show target tab content with animation
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.style.display = 'block';
        targetContent.classList.add('active', 'tab-content-animated');
      }
    });
  });

  // ============================================
  // MODAL ANIMATIONS
  // ============================================

  document.querySelectorAll('[data-modal]').forEach(trigger => {
    trigger.addEventListener('click', function() {
      const modalId = this.dataset.modal;
      const modal = document.getElementById(modalId);

      if (modal) {
        modal.classList.add('modal-overlay-animated', 'active');
        modal.querySelector('.modal-content').classList.add('modal-content-animated');
        document.body.style.overflow = 'hidden';
      }
    });
  });

  document.querySelectorAll('.modal-close').forEach(closeBtn => {
    closeBtn.addEventListener('click', function() {
      const modal = this.closest('.modal-overlay-animated');
      if (modal) {
        modal.classList.remove('active', 'modal-overlay-animated');
        modal.querySelector('.modal-content').classList.remove('modal-content-animated');
        document.body.style.overflow = '';
      }
    });
  });

  // Close modal on backdrop click
  document.querySelectorAll('.modal-overlay-animated').forEach(modal => {
    modal.addEventListener('click', function(e) {
      if (e.target === this) {
        this.classList.remove('active', 'modal-overlay-animated');
        this.querySelector('.modal-content').classList.remove('modal-content-animated');
        document.body.style.overflow = '';
      }
    });
  });

  // ============================================
  // TOAST NOTIFICATION ANIMATION
  // ============================================

  function showToast(message, type = 'info', duration = 5000) {
    const container = document.querySelector('.toast-container') || createToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast-animated ${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${getToastIcon(type)}</div>
      <div class="toast-message">${message}</div>
      <button class="toast-close">&times;</button>
    `;

    container.appendChild(toast);

    // Close button
    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.style.animation = 'slideOut 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    });

    // Auto remove
    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  }

  function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
  }

  function getToastIcon(type) {
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };
    return icons[type] || icons.info;
  }

  // Make showToast globally available
  window.showToast = showToast;

  // ============================================
  // SEARCH INPUT ANIMATION
  // ============================================

  const searchInputs = document.querySelectorAll('.search-input-animated');
  searchInputs.forEach(input => {
    input.addEventListener('focus', function() {
      this.parentElement.classList.add('focused');
    });

    input.addEventListener('blur', function() {
      if (!this.value) {
        this.parentElement.classList.remove('focused');
      }
    });
  });

  // ============================================
  // TABLE ROW HOVER EFFECTS
  // ============================================

  document.querySelectorAll('.table-animated tbody tr').forEach(row => {
    row.addEventListener('mouseenter', function() {
      this.style.backgroundColor = 'rgba(37, 99, 235, 0.1)';
      this.style.transform = 'scale(1.005)';
    });

    row.addEventListener('mouseleave', function() {
      this.style.backgroundColor = '';
      this.style.transform = '';
    });
  });

  // ============================================
  // KPI CARDS HOVER EFFECTS
  // ============================================

  document.querySelectorAll('.kpi-card-animated').forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-5px)';
      this.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.3), 0 0 20px rgba(37, 99, 235, 0.3)';
    });

    card.addEventListener('mouseleave', function() {
      this.style.transform = '';
      this.style.boxShadow = '';
    });
  });

  // ============================================
  // PROGRESS BAR ANIMATION ON SCROLL
  // ============================================

  const progressBars = document.querySelectorAll('.progress-animated');

  if (progressBars.length > 0) {
    const progressObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const bar = entry.target.querySelector('.progress-bar');
          if (bar) {
            const width = bar.dataset.width || '0%';
            bar.style.width = width;
            bar.classList.add('animated');
          }
        }
      });
    }, { threshold: 0.5 });

    progressBars.forEach(progress => {
      const bar = progress.querySelector('.progress-bar');
      if (bar) {
        bar.style.width = '0';
      }
      progressObserver.observe(progress);
    });
  }

  // ============================================
  // SKELETON LOADING
  // ============================================

  function showSkeleton(selector) {
    document.querySelectorAll(selector).forEach(el => {
      el.classList.add('skeleton');
    });
  }

  function hideSkeleton(selector) {
    document.querySelectorAll(selector).forEach(el => {
      el.classList.remove('skeleton');
    });
  }

  window.showSkeleton = showSkeleton;
  window.hideSkeleton = hideSkeleton;

  // ============================================
  // TOOLTIP INITIALIZATION
  // ============================================

  const tooltipElements = document.querySelectorAll('[data-tooltip]');
  tooltipElements.forEach(el => {
    el.classList.add('tooltip-animated');
  });

  // ============================================
  // PAGE TRANSITIONS
  // ============================================

  document.querySelectorAll('a:not([target="_blank"])').forEach(link => {
    const href = link.getAttribute('href');
    if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
      link.addEventListener('click', function() {
        document.body.classList.add('page-exiting');
      });
    }
  });

  // ============================================
  // FORM VALIDATION FEEDBACK
  // ============================================

  document.querySelectorAll('.input-animated').forEach(input => {
    input.addEventListener('invalid', function(e) {
      this.classList.add('error');
    });

    input.addEventListener('input', function() {
      this.classList.remove('error');
    });
  });

  // ============================================
  // PAGINATION ANIMATION
  // ============================================

  document.querySelectorAll('.pagination-btn-animated').forEach(btn => {
    btn.addEventListener('click', function() {
      const parent = this.closest('.pagination');
      parent.querySelectorAll('.pagination-btn-animated').forEach(b => {
        b.classList.remove('active');
      });
      this.classList.add('active');
    });
  });

  // ============================================
  // CHART ANIMATION (if chart.js or similar)
  // ============================================

  window.animateChart = function(chart) {
    if (chart && chart.update) {
      chart.update('active');
    }
  };

  // ============================================
  // FILTER BUTTONS ANIMATION
  // ============================================

  document.querySelectorAll('.filter-btn-animated').forEach(btn => {
    btn.addEventListener('click', function() {
      const parent = this.closest('.filter-group');
      if (parent) {
        parent.querySelectorAll('.filter-btn-animated').forEach(b => {
          b.classList.remove('active');
        });
      }
      this.classList.add('active');
    });
  });

  // ============================================
  // KEYBOARD NAVIGATION
  // ============================================

  document.addEventListener('keydown', function(e) {
    // Escape closes modals
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay-animated.active').forEach(modal => {
        modal.classList.remove('active');
        document.body.style.overflow = '';
      });
    }
  });

  // ============================================
  // REDUCE MOTION CHECK
  // ============================================

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (prefersReducedMotion.matches) {
    document.documentElement.style.setProperty('--transition-fast', '0ms');
    document.documentElement.style.setProperty('--transition-base', '0ms');
    document.documentElement.style.setProperty('--transition-slow', '0ms');
  }

  // ============================================
  // INITIAL PAGE LOAD ANIMATION
  // ============================================

  setTimeout(() => {
    document.body.classList.add('loaded');
  }, 100);

});

// CSS for slideOut animation
const style = document.createElement('style');
style.textContent = `
  @keyframes slideOut {
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(100%);
    }
  }

  .toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .toast-animated {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    background: var(--bg-card, #1e293b);
    border-radius: 8px;
    color: var(--text-primary, #f8fafc);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    min-width: 300px;
    max-width: 450px;
  }

  .toast-icon {
    font-size: 1.2rem;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
  }

  .toast-animated.success .toast-icon {
    background: rgba(16, 185, 129, 0.2);
    color: #10b981;
  }

  .toast-animated.error .toast-icon {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
  }

  .toast-animated.warning .toast-icon {
    background: rgba(245, 158, 11, 0.2);
    color: #f59e0b;
  }

  .toast-animated.info .toast-icon {
    background: rgba(37, 99, 235, 0.2);
    color: #2563eb;
  }

  .toast-message {
    flex: 1;
    font-size: 0.9rem;
  }

  .toast-close {
    background: none;
    border: none;
    color: var(--text-secondary, #94a3b8);
    font-size: 1.2rem;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
    transition: color 0.2s;
  }

  .toast-close:hover {
    color: var(--text-primary, #f8fafc);
  }

  .scroll-top {
    position: fixed;
    bottom: 30px;
    right: 30px;
    width: 45px;
    height: 45px;
    background: var(--primary, #2563eb);
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 5px 20px rgba(37, 99, 235, 0.4);
    z-index: 1000;
  }

  .scroll-top.visible {
    opacity: 1;
    visibility: visible;
  }

  .scroll-top:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(37, 99, 235, 0.5);
  }

  .sidebar.collapsed {
    width: 60px !important;
  }

  .sidebar.collapsed .nav-text,
  .sidebar.collapsed .sidebar-title {
    display: none;
  }
`;
document.head.appendChild(style);

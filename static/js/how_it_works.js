/**
 * ============================================================================
 * VITALIS AI — HOW IT WORKS PREMIUM INTERACTIVE REDESIGN JAVASCRIPT
 * React Bits inspired interactions:
 * - Scroll Reveal (IntersectionObserver with stagger support)
 * - Spotlight Card (cursor-aware radial highlight with local coordinates)
 * - Depth Card (subtle 3D perspective tilt with damping)
 * - Count Up (cubic eased number transition for Wellness Score)
 * - Multi-horizon Progress Trend SVG path redraw
 * - Localized Three.js ShapeBlur WebGL lifecycle integration
 * ============================================================================
 */

(function () {
  'use strict';

  // Check user preferences
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isTouchDevice = window.matchMedia('(hover: none)').matches;

  /**
   * 1. SCROLL REVEAL OBSERVER
   */
  function initScrollReveal() {
    const revealElements = document.querySelectorAll('.hiw-reveal');
    if (!revealElements.length) return;

    if (prefersReducedMotion) {
      revealElements.forEach(el => el.classList.add('is-revealed'));
      return;
    }

    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          obs.unobserve(entry.target);
        }
      });
    }, {
      root: null,
      rootMargin: '0px 0px -8% 0px',
      threshold: 0.12
    });

    revealElements.forEach(el => observer.observe(el));
  }

  /**
   * 2. SPOTLIGHT & DEPTH CARD HOVER
   * React Bits Spotlight Card & Depth Card adaptation
   */
  function initSpotlightAndDepthCards() {
    if (isTouchDevice || prefersReducedMotion) return;

    const cards = document.querySelectorAll('.hiw-interactive-card');
    cards.forEach(card => {
      let isHovered = false;
      let rafId = null;

      function onPointerMove(e) {
        if (!isHovered) return;
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Spotlight CSS custom properties
        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);

        // Subtle 3D Depth Card tilt (max 3 degrees)
        if (card.classList.contains('hiw-depth-card')) {
          const centerX = rect.width / 2;
          const centerY = rect.height / 2;
          const tiltX = ((y - centerY) / centerY) * -2.5;
          const tiltY = ((x - centerX) / centerX) * 2.5;

          if (rafId) cancelAnimationFrame(rafId);
          rafId = requestAnimationFrame(() => {
            card.style.transform = `perspective(1000px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg) translateY(-2px)`;
          });
        }
      }

      function onPointerEnter() {
        isHovered = true;
      }

      function onPointerLeave() {
        isHovered = false;
        if (rafId) cancelAnimationFrame(rafId);
        if (card.classList.contains('hiw-depth-card')) {
          card.style.transform = '';
        }
      }

      card.addEventListener('pointerenter', onPointerEnter);
      card.addEventListener('pointermove', onPointerMove);
      card.addEventListener('pointerleave', onPointerLeave);
    });
  }

  /**
   * 3. SCROLL STACK & CAPABILITY NAV
   * Watches the 5 core capability cards as user scrolls.
   */
  function initScrollStack() {
    const stackCards = document.querySelectorAll('.hiw-stack-card');
    const navButtons = document.querySelectorAll('.hiw-stack-nav-btn');
    if (!stackCards.length) return;

    // Fast-jump click listeners
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        const targetCard = document.getElementById(targetId);
        if (targetCard) {
          const navOffset = 90;
          const targetY = targetCard.getBoundingClientRect().top + window.pageYOffset - navOffset;
          window.scrollTo({ top: targetY, behavior: 'smooth' });
        }
      });
    });

    if (prefersReducedMotion) return;

    // Observe active stack card
    const stackObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const cardId = entry.target.id;
        const navBtn = document.querySelector(`.hiw-stack-nav-btn[data-target="${cardId}"]`);

        if (entry.isIntersecting && entry.intersectionRatio >= 0.35) {
          navButtons.forEach(b => b.classList.remove('is-active'));
          if (navBtn) navBtn.classList.add('is-active');

          // Trigger card-specific visual activations
          if (cardId === 'info-wellness-score') {
            triggerWellnessScoreAnimation();
          } else if (cardId === 'info-progress-trends') {
            triggerTrendAnimation();
          }
        }
      });
    }, {
      root: null,
      threshold: [0.35, 0.6]
    });

    stackCards.forEach(card => stackObserver.observe(card));
  }

  /**
   * 4. WELLNESS SCORE COUNT UP & RADIAL GAUGE
   * React Bits Count Up adaptation
   */
  let scoreAnimated = false;
  function triggerWellnessScoreAnimation() {
    if (scoreAnimated) return;
    scoreAnimated = true;

    const numEl = document.getElementById('hiw-score-num');
    const radialVal = document.getElementById('hiw-radial-val');
    const dimBars = document.querySelectorAll('.hiw-dim-bar');

    const targetScore = 78;
    const duration = 1200; // ms

    if (prefersReducedMotion || !numEl) {
      if (numEl) numEl.textContent = targetScore;
      if (radialVal) radialVal.style.strokeDashoffset = '83';
      dimBars.forEach(bar => {
        const targetW = bar.getAttribute('data-pct');
        bar.style.width = targetW ? `${targetW}%` : '80%';
      });
      return;
    }

    const startTime = performance.now();

    function updateCount(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out: 1 - pow(1 - p, 3)
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      const currentVal = Math.round(easeProgress * targetScore);

      numEl.textContent = currentVal;

      if (progress < 1) {
        requestAnimationFrame(updateCount);
      } else {
        numEl.textContent = targetScore;
      }
    }

    requestAnimationFrame(updateCount);

    // Animate SVG radial circle (circumference = 2 * PI * 60 ~= 377)
    if (radialVal) {
      const targetOffset = 377 - (377 * (targetScore / 100));
      radialVal.style.strokeDashoffset = targetOffset.toFixed(1);
    }

    // Animate dimension bars
    dimBars.forEach(bar => {
      const targetW = bar.getAttribute('data-pct');
      if (targetW) {
        bar.style.width = `${targetW}%`;
      }
    });
  }

  /**
   * 5. PROGRESS TRENDS MULTI-HORIZON INTERACTION
   */
  const trendPaths = {
    '7d': {
      d: 'M 30,110 Q 80,95 140,80 T 260,65 T 380,50 T 470,35',
      areaD: 'M 30,110 Q 80,95 140,80 T 260,65 T 380,50 T 470,35 L 470,140 L 30,140 Z',
      dots: [
        { cx: 30, cy: 110 }, { cx: 140, cy: 80 }, { cx: 260, cy: 65 }, { cx: 380, cy: 50 }, { cx: 470, cy: 35 }
      ]
    },
    '14d': {
      d: 'M 30,120 Q 90,105 160,100 T 270,75 T 370,60 T 470,42',
      areaD: 'M 30,120 Q 90,105 160,100 T 270,75 T 370,60 T 470,42 L 470,140 L 30,140 Z',
      dots: [
        { cx: 30, cy: 120 }, { cx: 160, cy: 100 }, { cx: 270, cy: 75 }, { cx: 370, cy: 60 }, { cx: 470, cy: 42 }
      ]
    },
    '30d': {
      d: 'M 30,125 Q 110,115 190,85 T 300,70 T 390,55 T 470,30',
      areaD: 'M 30,125 Q 110,115 190,85 T 300,70 T 390,55 T 470,30 L 470,140 L 30,140 Z',
      dots: [
        { cx: 30, cy: 125 }, { cx: 190, cy: 85 }, { cx: 300, cy: 70 }, { cx: 390, cy: 55 }, { cx: 470, cy: 30 }
      ]
    }
  };

  let trendAnimated = false;
  function triggerTrendAnimation(horizon = '7d') {
    const pathEl = document.getElementById('hiw-trend-path');
    const areaEl = document.getElementById('hiw-trend-area');
    const ptsEl = document.getElementById('hiw-trend-pts');
    if (!pathEl) return;

    const data = trendPaths[horizon] || trendPaths['7d'];

    if (prefersReducedMotion) {
      pathEl.setAttribute('d', data.d);
      pathEl.style.strokeDashoffset = '0';
      if (areaEl) areaEl.setAttribute('d', data.areaD);
      renderTrendDots(ptsEl, data.dots);
      return;
    }

    pathEl.setAttribute('d', data.d);
    if (areaEl) areaEl.setAttribute('d', data.areaD);
    renderTrendDots(ptsEl, data.dots);

    // Redraw animation
    pathEl.style.transition = 'none';
    pathEl.style.strokeDashoffset = '600';
    // Force layout reflow
    void pathEl.getBoundingClientRect();
    pathEl.style.transition = 'stroke-dashoffset 1.3s cubic-bezier(0.16, 1, 0.3, 1)';
    pathEl.style.strokeDashoffset = '0';

    trendAnimated = true;
  }

  function renderTrendDots(container, dots) {
    if (!container || !dots) return;
    container.innerHTML = '';
    dots.forEach(pt => {
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', pt.cx);
      circle.setAttribute('cy', pt.cy);
      circle.setAttribute('r', '4');
      container.appendChild(circle);
    });
  }

  function initTrendTabs() {
    const tabBtns = document.querySelectorAll('.hiw-tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const horizon = btn.getAttribute('data-horizon');
        triggerTrendAnimation(horizon);
      });
    });
  }

  /**
   * 6. TECHNICAL ARCHITECTURE INTERACTIVE FLOW
   */
  function initTechnicalArchitectureNodes() {
    const techNodes = document.querySelectorAll('.hiw-tech-node-item');
    const descBox = document.getElementById('hiw-tech-selected-desc');
    if (!techNodes.length) return;

    const nodeDescriptions = {
      'user-data': 'Tracks daily wellness data (movement, sleep, hydration, completed daily tasks) through standard logging.',
      'profile-activity': 'Consolidates profile biometrics, primary wellness goals, allergies, and recent logging frequency.',
      'personalization': 'Matches activity patterns and lifestyle targets with tailored micro-goals and routine pacing.',
      'ml-processing': 'Gradient boosting recommendation inference and unsupervised Isolation Forest outlier monitoring.',
      'safety-constraints': 'Filters out unsuitable suggestions based on known sensitivities, constraints, and contraindicated foods.',
      'guidance': 'Presents actionable, achievable recommendations alongside transparent explainability reasoning.',
      'auditability': 'Logs input feature vectors, active model artifact hashes, and confidence calibration scores.'
    };

    techNodes.forEach(node => {
      node.addEventListener('click', () => {
        techNodes.forEach(n => n.classList.remove('is-active'));
        node.classList.add('is-active');
        const key = node.getAttribute('data-node');
        if (descBox && nodeDescriptions[key]) {
          descBox.textContent = nodeDescriptions[key];
        }
      });
    });
  }

  /**
   * 7. SHAPEBLUR INTEGRATION (Localized Accent)
   * Uses existing VitalisShapeBlur implementation from main.js when available
   */
  let hiwShapeBlurInstance = null;
  function initShapeBlurAccent() {
    if (prefersReducedMotion || isTouchDevice) return;

    const mount = document.getElementById('hiw-hero-shapeblur');
    if (!mount) return;

    // Check if window.VitalisShapeBlur and THREE exist
    if (typeof window.VitalisShapeBlur !== 'undefined' && typeof THREE !== 'undefined') {
      try {
        hiwShapeBlurInstance = new window.VitalisShapeBlur(mount, {
          variation: 2,         // Pure circular variation
          pixelRatioProp: 1.5,
          shapeSize: 0.38,
          roundness: 0.5,
          borderSize: 0.05,
          circleSize: 0.32,
          circleEdge: 0.45,
          color: '#10b981',     // Vitalis teal
          color2: '#06b6d4'     // Vitalis cyan
        });

        // Use IntersectionObserver to pause when off-screen for maximum performance
        const obs = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (hiwShapeBlurInstance) {
              if (entry.isIntersecting) {
                hiwShapeBlurInstance.resume();
              } else {
                hiwShapeBlurInstance.pause();
              }
            }
          });
        }, { threshold: 0.05 });

        obs.observe(mount);
      } catch (err) {
        console.warn('HowItWorks ShapeBlur notice:', err);
      }
    }
  }

  // Teardown / cleanup
  window.addEventListener('beforeunload', () => {
    if (hiwShapeBlurInstance) {
      hiwShapeBlurInstance.destroy();
      hiwShapeBlurInstance = null;
    }
  });

  // Main initialization on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    initSpotlightAndDepthCards();
    initScrollStack();
    initTrendTabs();
    initTechnicalArchitectureNodes();
    initShapeBlurAccent();
  });

})();

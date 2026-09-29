/**
 * Vitalis AI Minimal Loading Component & Application Interactions
 * 
 * Reusable minimal pulse loading system:
 * - Pure white ECG/pulse stroke on transparent background
 * - Exactly follows Vitalis pulse geometry (M2 12h4l3-9 6 18 3-9h4)
 * - Pure CSS/SVG stroke-dashoffset animation (0.9s cycle)
 * - Accessible with prefers-reduced-motion support
 * - Immediate rendering opportunity on navigation tabs with requestAnimationFrame
 * - Reusable across:
 *   1. Page/navigation loading (Dashboard, Activity, Recommendations, Progress, Reports, Assistant, Profile, etc.)
 *   2. Same-page tabs (minimum perceptible visible duration 250-400ms)
 *   3. API requests
 *   4. Dashboard data loading
 *   5. AI recommendation generation
 *   6. Wellness score calculation
 *   7. Report generation
 *   8. Form submission
 *   9. Saving activity
 *   10. Assistant responses
 */

(function(window) {
  'use strict';

  // Geometry: short baseline, sharp upward peak, sharp downward peak, short ending
  const PULSE_PATH = 'M2 12h4l3-9 6 18 3-9h4';

  let isNavigating = false;
  let hooksInitialized = false;

  const VitalisLoader = {
    /**
     * Generate inline SVG string for the minimal pulse loader
     * @param {string} sizeClass - Optional: 'vitalis-loader-sm' (buttons), 'vitalis-loader-lg' (overlays), or '' (standard)
     * @param {string} extraClass - Optional extra CSS class
     * @returns {string} Inline SVG string
     */
    getSvgString(sizeClass = '', extraClass = '') {
      const classes = ['vitalis-loader-svg', sizeClass, extraClass].filter(Boolean).join(' ');
      return `<svg class="${classes}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" role="status" aria-label="Loading"><path class="vitalis-loading-pulse" d="${PULSE_PATH}" pathLength="100"/></svg>`;
    },

    /**
     * Create an SVG DOM element for the minimal pulse loader
     */
    createSvgElement(sizeClass = '', extraClass = '') {
      const temp = document.createElement('div');
      temp.innerHTML = this.getSvgString(sizeClass, extraClass).trim();
      return temp.firstElementChild;
    },

    /**
     * HTML helper for inline block loading states
     */
    inlineHtml(sizeClass = '', extraClass = '') {
      return `<div class="vitalis-loader-inline" role="status" aria-label="Loading">${this.getSvgString(sizeClass, extraClass)}</div>`;
    },

    // Internal state tracking
    _overlayTimer: null,
    _activeRequests: 0,

    /**
     * Show global overlay
     * @param {number} delayMs - Delay before showing overlay. 0 means IMMEDIATELY.
     */
    showOverlay(delayMs = 0) {
      this._activeRequests++;
      const overlay = document.getElementById('vitalis-global-overlay');
      if (!overlay) return;

      if (delayMs <= 0) {
        if (this._overlayTimer) {
          clearTimeout(this._overlayTimer);
          this._overlayTimer = null;
        }
        overlay.classList.add('active');
        overlay.setAttribute('aria-hidden', 'false');
        return;
      }

      if (!this._overlayTimer && !overlay.classList.contains('active')) {
        this._overlayTimer = setTimeout(() => {
          if (this._activeRequests > 0) {
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
          }
          this._overlayTimer = null;
        }, delayMs);
      }
    },

    /**
     * Hide global overlay
     * @param {boolean} force - Force immediate hide regardless of active request count
     */
    hideOverlay(force = false) {
      if (force) {
        this._activeRequests = 0;
      } else {
        this._activeRequests = Math.max(0, this._activeRequests - 1);
      }

      if (this._activeRequests === 0) {
        if (this._overlayTimer) {
          clearTimeout(this._overlayTimer);
          this._overlayTimer = null;
        }
        const overlay = document.getElementById('vitalis-global-overlay');
        if (overlay) {
          overlay.classList.remove('active');
          overlay.setAttribute('aria-hidden', 'true');
        }
      }
    },

    /**
     * Set a button into loading state with the minimal pulse loader
     * Preserves button dimensions, hides label, renders white pulse in center
     */
    setButtonLoading(button, isLoading = true) {
      if (!button) return;

      if (isLoading) {
        if (button.classList.contains('is-loading')) return;

        // Wrap existing text/content if not already wrapped
        if (!button.querySelector('.btn-text-content')) {
          const wrapper = document.createElement('span');
          wrapper.className = 'btn-text-content';
          while (button.firstChild) {
            wrapper.appendChild(button.firstChild);
          }
          button.appendChild(wrapper);
        }

        // Add pulse loader container if not present
        let loader = button.querySelector('.btn-loader-pulse-container');
        if (!loader) {
          loader = document.createElement('span');
          loader.className = 'btn-loader-pulse-container';
          loader.setAttribute('aria-hidden', 'true');
          loader.innerHTML = this.getSvgString('vitalis-loader-sm');
          button.appendChild(loader);
        }

        button.classList.add('is-loading');
        button.setAttribute('aria-busy', 'true');
      } else {
        button.classList.remove('is-loading');
        button.removeAttribute('aria-busy');
        const loader = button.querySelector('.btn-loader-pulse-container');
        if (loader) {
          loader.remove();
        }
      }
    },

    /**
     * Wrap any Promise or async task with loader handling
     */
    async track(promise, options = {}) {
      const { button = null, overlay = false, delayMs = 0 } = options;
      if (button) this.setButtonLoading(button, true);
      if (overlay) this.showOverlay(delayMs);

      try {
        return await promise;
      } finally {
        if (button) this.setButtonLoading(button, false);
        if (overlay) this.hideOverlay();
      }
    },

    /**
     * Switch same-page tab with perceptible pulse loader
     * @param {Function} switchFn - Action to switch/render the tab content
     * @param {number} minDurationMs - Minimum duration to show pulse (default 300ms)
     */
    async switchTab(switchFn, minDurationMs = 300) {
      this.showOverlay(0);
      const startTime = performance.now();
      try {
        if (typeof switchFn === 'function') {
          await switchFn();
        }
      } finally {
        const elapsed = performance.now() - startTime;
        const remaining = Math.max(0, minDurationMs - elapsed);
        setTimeout(() => {
          this.hideOverlay(true);
        }, remaining);
      }
    },

    /**
     * Check if a clicked link is a genuine navigational link
     */
    isNavigationalLink(link, e) {
      if (!link || !link.href) return false;

      // Ignore modified clicks (open in new tab/window, save, etc.)
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.defaultPrevented) {
        return false;
      }

      // Check element attributes
      if (link.target && link.target !== '_self') return false;
      if (link.hasAttribute('download')) return false;
      if (link.dataset.noLoader !== undefined) return false;
      if (link.getAttribute('role') === 'button' && !link.getAttribute('href')) return false;

      // Ignore dropdowns, modals, and toggles
      if (link.hasAttribute('data-toggle') || link.hasAttribute('data-bs-toggle') || link.classList.contains('dropdown-toggle')) {
        return false;
      }

      // Check href string
      const href = link.getAttribute('href');
      if (!href || href === '#' || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) {
        return false;
      }

      // Exclude logout link per requirement
      if (href.includes('logout') || link.id === 'btn-logout') {
        return false;
      }

      // Check parsed URL
      try {
        const url = new URL(link.href, window.location.origin);
        // Exclude external domains
        if (url.origin !== window.location.origin) return false;
        // Exclude same URL (clicking active page again)
        if (url.pathname === window.location.pathname && url.search === window.location.search) {
          return false;
        }
        return true;
      } catch (err) {
        return false;
      }
    },

    /**
     * Trigger immediate navigation loading with double rAF paint guarantee
     */
    triggerNavigation(targetHref) {
      if (isNavigating) return;
      isNavigating = true;

      // Immediately show overlay with 0ms delay
      VitalisLoader.showOverlay(0);

      const startTime = performance.now();
      // 200ms ensures the 100ms opacity transition completes and the white pulse is visibly perceived
      const MIN_NAV_VISIBLE_MS = 200;

      // Double requestAnimationFrame ensures the browser submits and paints the loader frame before navigation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const elapsed = performance.now() - startTime;
          const remaining = Math.max(0, MIN_NAV_VISIBLE_MS - elapsed);
          setTimeout(() => {
            window.location.href = targetHref;
          }, remaining);
        });
      });

      // Safety timeout in case navigation is interrupted or cancelled
      setTimeout(() => {
        isNavigating = false;
        VitalisLoader.hideOverlay(true);
      }, 7000);
    },

    /**
     * Initialize automatic hooks for forms, navigation tabs, and same-page tabs
     */
    initAutoHooks() {
      if (hooksInitialized) return;
      hooksInitialized = true;

      // 1. Primary navigation link clicks: immediately show pulse loader with paint opportunity
      document.addEventListener('click', (e) => {
        // Exclude clicks on unrelated buttons or dropdowns
        const button = e.target.closest('button');
        if (button && !e.target.closest('a')) {
          return;
        }

        const link = e.target.closest('a');
        if (!link) return;

        // Check for same-page tabs (e.g. [role="tab"], .nav-tab, [data-tab-target])
        const tab = link.closest('[role="tab"], .nav-tab, .same-page-tab, [data-tab-target], [data-tab]');
        if (tab) {
          const href = link.getAttribute('href');
          if (!href || href.startsWith('#')) {
            // Same-page tab switch: show pulse for 300ms minimum visible time
            VitalisLoader.showOverlay(0);
            setTimeout(() => {
              VitalisLoader.hideOverlay(true);
            }, 300);
            return;
          }
        }

        // Check if genuine navigation link
        if (VitalisLoader.isNavigationalLink(link, e)) {
          e.preventDefault();
          VitalisLoader.triggerNavigation(link.href);
        }
      });

      // 2. Form submission loader on buttons
      document.addEventListener('submit', (e) => {
        const form = e.target;
        if (!form || form.dataset.noLoader !== undefined) return;

        // Find primary submit button
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
          VitalisLoader.setButtonLoading(submitBtn, true);
        }

        // Show overlay if form navigation takes longer than 250ms
        VitalisLoader.showOverlay(250);
      });

      // Reset loading state if browser form validation fails
      document.addEventListener('invalid', () => {
        VitalisLoader.hideOverlay(true);
        const loadingButtons = document.querySelectorAll('.btn.is-loading, button.is-loading');
        loadingButtons.forEach(btn => VitalisLoader.setButtonLoading(btn, false));
      }, true);

      // 3. Clear overlay on pageshow (bfcache) and popstate (browser back/forward controls)
      window.addEventListener('pageshow', () => {
        isNavigating = false;
        VitalisLoader.hideOverlay(true);
      });

      window.addEventListener('popstate', () => {
        isNavigating = false;
        VitalisLoader.hideOverlay(true);
      });
    }
  };

  window.VitalisLoader = VitalisLoader;

  // Initialize auto hooks once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => VitalisLoader.initAutoHooks());
  } else {
    VitalisLoader.initAutoHooks();
  }
})(window);

// General UI interactions
document.addEventListener('DOMContentLoaded', () => {
  // Auto-dismiss success flash messages after 6 seconds
  const flashAlerts = document.querySelectorAll('.alert-success, .alert-info');
  flashAlerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });

  // Highlight active form controls
  const inputs = document.querySelectorAll('.form-control, .form-select');
  inputs.forEach(input => {
    input.addEventListener('focus', () => {
      const group = input.closest('.form-group');
      if (group) {
        const label = group.querySelector('.form-label');
        if (label) label.style.color = 'var(--accent-teal)';
      }
    });
    input.addEventListener('blur', () => {
      const group = input.closest('.form-group');
      if (group) {
        const label = group.querySelector('.form-label');
        if (label) label.style.color = 'var(--text-secondary)';
      }
    });
  });
});

/**
 * React Bits ShapeBlur WebGL Shader adaptation for Vitalis AI Companion
 * Directly based on React Bits ShapeBlur component:
 * - Three.js WebGLRenderer with alpha transparency
 * - ShaderMaterial with vertexShader & fragmentShader
 * - Signed distance field functions: sdRoundRect, sdCircle, sdPoly
 * - Anti-aliasing stroke and fill functions: strokeAA, fill, aastep
 * - Local component coordinates: rect = mount.getBoundingClientRect()
 * - Damped mouse coordinates via THREE.MathUtils.damp(...)
 * - Dynamic uniforms: u_mouse, u_resolution, u_pixelRatio, u_shapeSize,
 *   u_roundness, u_borderSize, u_circleSize, u_circleEdge, u_color, u_color2
 * - Continuous requestAnimationFrame rendering loop with pause/resume support
 * - ResizeObserver support with automatic renderer & camera updates
 * - Full cleanup and resource disposal: geometry, material, renderer, forceContextLoss
 */
class VitalisShapeBlur {
  constructor(mount, options = {}) {
    this.mount = mount;
    this.options = Object.assign({
      variation: 2,       // Pure circular variation
      pixelRatioProp: 2,
      shapeSize: 0.48,     // Circular radius factor (diameter 67px around 58px button)
      roundness: 0.5,
      borderSize: 0.045,   // Pure circular stroke width
      circleSize: 0.35,    // Mouse circle influence size
      circleEdge: 0.52,    // Blur edge softness
      color: '#06b6d4',    // Vitalis cyan
      color2: '#8b5cf6'    // Vitalis purple
    }, options);

    this.active = false;
    this.paused = false;
    this.animationFrameId = null;
    this.time = 0;
    this.lastTime = 0;

    this.vMouse = null;
    this.vMouseDamp = null;
    this.vResolution = null;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.geo = null;
    this.material = null;
    this.quad = null;
    this.ro = null;

    this._onPointerMove = this._handlePointerMove.bind(this);
    this._onResize = this.resize.bind(this);
    this._onMouseLeave = this._handleMouseLeave.bind(this);

    this.init();
  }

  static get vertexShader() {
    return `
varying vec2 v_texcoord;
void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    v_texcoord = uv;
}
`;
  }

  static get fragmentShader() {
    return `
varying vec2 v_texcoord;

uniform vec2 u_mouse;
uniform vec2 u_resolution;
uniform float u_pixelRatio;

uniform float u_shapeSize;
uniform float u_roundness;
uniform float u_borderSize;
uniform float u_circleSize;
uniform float u_circleEdge;

uniform vec3 u_color;
uniform vec3 u_color2;

#ifndef PI
#define PI 3.1415926535897932384626433832795
#endif
#ifndef TWO_PI
#define TWO_PI 6.2831853071795864769252867665590
#endif

#ifndef VAR
#define VAR 2
#endif

#ifndef FNC_COORD
#define FNC_COORD
vec2 coord(in vec2 p) {
    p = p / u_resolution.xy;
    if (u_resolution.x > u_resolution.y) {
        p.x *= u_resolution.x / u_resolution.y;
        p.x += (u_resolution.y - u_resolution.x) / u_resolution.y / 2.0;
    } else {
        p.y *= u_resolution.y / u_resolution.x;
        p.y += (u_resolution.x - u_resolution.y) / u_resolution.x / 2.0;
    }
    p -= 0.5;
    p *= vec2(-1.0, 1.0);
    return p;
}
#endif

#define st0 coord(gl_FragCoord.xy)
#define mx coord(u_mouse * u_pixelRatio)

float sdCircle(in vec2 st, in vec2 center) {
    return length(st - center) * 2.0;
}
float sdPoly(in vec2 p, in float w, in int sides) {
    float a = atan(p.x, p.y) + PI;
    float r = TWO_PI / float(sides);
    float d = cos(floor(0.5 + a / r) * r - a) * length(max(abs(p) * 1.0, 0.0));
    return d * 2.0 - w;
}

float aastep(float threshold, float value) {
    float afwidth = length(vec2(dFdx(value), dFdy(value))) * 0.70710678118654757;
    return smoothstep(threshold - afwidth, threshold + afwidth, value);
}
float fill(in float x) { return 1.0 - aastep(0.0, x); }
float fill(float x, float size, float edge) {
    return 1.0 - smoothstep(size - edge, size + edge, x);
}
float stroke(in float d, in float t) { return (1.0 - aastep(t, abs(d))); }
float stroke(float x, float size, float w, float edge) {
    float d = smoothstep(size - edge, size + edge, x + w * 0.5) - smoothstep(size - edge, size + edge, x - w * 0.5);
    return clamp(d, 0.0, 1.0);
}

float strokeAA(float x, float size, float w, float edge) {
    float afwidth = length(vec2(dFdx(x), dFdy(x))) * 0.70710678;
    float d = smoothstep(size - edge - afwidth, size + edge + afwidth, x + w * 0.5)
            - smoothstep(size - edge - afwidth, size + edge + afwidth, x - w * 0.5);
    return clamp(d, 0.0, 1.0);
}

void main() {
    vec2 st = st0 + 0.5;
    vec2 posMouse = mx * vec2(1., -1.) + 0.5;

    float size = u_shapeSize;
    float borderSize = u_borderSize;
    float circleSize = u_circleSize;
    float circleEdge = u_circleEdge;

    float sdfCircle = fill(
        sdCircle(st, posMouse),
        circleSize,
        circleEdge
    );

    // 100% Circular Signed Distance Field and strokeAA
    float sdf;
    if (VAR == 1) {
        sdf = sdCircle(st, vec2(0.5));
        sdf = fill(sdf, size, sdfCircle) * 1.2;
    } else if (VAR == 3) {
        sdf = sdPoly(st - vec2(0.5, 0.45), 0.3, 3);
        sdf = fill(sdf, 0.05, sdfCircle) * 1.4;
    } else {
        // Pure circle stroke blur (VAR 0 and VAR 2)
        sdf = sdCircle(st, vec2(0.5));
        sdf = strokeAA(sdf, size, borderSize, sdfCircle) * 4.0;
    }

    vec3 color = mix(u_color, u_color2, clamp(st.y + st.x * 0.25, 0.0, 1.0));
    color = mix(color, vec3(1.0), clamp(sdfCircle * 0.35, 0.0, 1.0));
    float alpha = sdf;
    gl_FragColor = vec4(color.rgb, alpha);
}
`;
  }

  init() {
    if (!this.mount) return;
    if (typeof THREE === 'undefined') {
      return;
    }

    try {
      this.active = true;

      this.vMouse = new THREE.Vector2(-9999, -9999);
      this.vMouseDamp = new THREE.Vector2(-9999, -9999);
      this.vResolution = new THREE.Vector2();

      this.scene = new THREE.Scene();
      this.camera = new THREE.OrthographicCamera();
      this.camera.position.z = 1;

      this.renderer = new THREE.WebGLRenderer({ 
        alpha: true, 
        antialias: true,
        powerPreference: 'low-power'
      });
      this.renderer.setClearColor(0x000000, 0);
      this.renderer.domElement.style.pointerEvents = 'none';
      this.mount.appendChild(this.renderer.domElement);

      const color1 = new THREE.Color(this.options.color);
      const color2 = new THREE.Color(this.options.color2);

      this.geo = new THREE.PlaneGeometry(1, 1);
      this.material = new THREE.ShaderMaterial({
        vertexShader: VitalisShapeBlur.vertexShader,
        fragmentShader: VitalisShapeBlur.fragmentShader,
        uniforms: {
          u_mouse: { value: this.vMouseDamp },
          u_resolution: { value: this.vResolution },
          u_pixelRatio: { value: this.options.pixelRatioProp },
          u_shapeSize: { value: this.options.shapeSize },
          u_roundness: { value: this.options.roundness },
          u_borderSize: { value: this.options.borderSize },
          u_circleSize: { value: this.options.circleSize },
          u_circleEdge: { value: this.options.circleEdge },
          u_color: { value: new THREE.Vector3(color1.r, color1.g, color1.b) },
          u_color2: { value: new THREE.Vector3(color2.r, color2.g, color2.b) }
        },
        defines: { 
          VAR: parseInt(this.options.variation, 10) || 0 
        },
        extensions: {
          derivatives: true
        },
        transparent: true
      });

      this.quad = new THREE.Mesh(this.geo, this.material);
      this.scene.add(this.quad);

      document.addEventListener('mousemove', this._onPointerMove, { passive: true });
      document.addEventListener('pointermove', this._onPointerMove, { passive: true });
      document.addEventListener('mouseleave', this._onMouseLeave, { passive: true });
      window.addEventListener('resize', this._onResize, { passive: true });

      if (typeof ResizeObserver !== 'undefined') {
        this.ro = new ResizeObserver(() => {
          if (!this.active) return;
          this.resize();
        });
        this.ro.observe(this.mount);
      }

      this.resize();

      // Respect prefers-reduced-motion
      const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (prefersReducedMotion) {
        this.vMouse.set(this.mount.clientWidth * 0.5, this.mount.clientHeight * 0.5);
        this.vMouseDamp.copy(this.vMouse);
        this.renderer.render(this.scene, this.camera);
        return;
      }

      // Respect touch-only devices: render static frame and conserve energy
      const isTouchOnly = window.matchMedia && window.matchMedia('(hover: none) and (pointer: coarse)').matches;
      if (isTouchOnly) {
        this.vMouse.set(this.mount.clientWidth * 0.5, this.mount.clientHeight * 0.5);
        this.vMouseDamp.copy(this.vMouse);
        this.renderer.render(this.scene, this.camera);
        return;
      }

      this.lastTime = performance.now() * 0.001;
      this.startLoop();
    } catch (err) {
      console.warn('VitalisShapeBlur WebGL initialization notice:', err);
    }
  }

  _handlePointerMove(e) {
    if (!this.active || !this.mount) return;
    const rect = this.mount.getBoundingClientRect();
    this.vMouse.set(e.clientX - rect.left, e.clientY - rect.top);
  }

  _handleMouseLeave() {
    if (!this.active || !this.vMouse) return;
    this.vMouse.set(-9999, -9999);
  }

  resize() {
    if (!this.active || !this.mount || !this.renderer) return;
    const w = this.mount.clientWidth || 140;
    const h = this.mount.clientHeight || 140;
    const dpr = Math.min(window.devicePixelRatio || 1, this.options.pixelRatioProp || 2);

    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(dpr);

    this.camera.left = -w / 2;
    this.camera.right = w / 2;
    this.camera.top = h / 2;
    this.camera.bottom = -h / 2;
    this.camera.updateProjectionMatrix();

    if (this.quad) {
      this.quad.scale.set(w, h, 1);
    }
    if (this.vResolution) {
      this.vResolution.set(w, h).multiplyScalar(dpr);
    }
    if (this.material && this.material.uniforms && this.material.uniforms.u_pixelRatio) {
      this.material.uniforms.u_pixelRatio.value = dpr;
    }
  }

  update() {
    if (!this.active || this.paused) return;

    this.time = performance.now() * 0.001;
    const dt = Math.min(this.time - this.lastTime, 0.1);
    this.lastTime = this.time;

    if (this.vMouseDamp && this.vMouse) {
      ['x', 'y'].forEach(k => {
        this.vMouseDamp[k] = THREE.MathUtils.damp(this.vMouseDamp[k], this.vMouse[k], 8, dt);
      });
    }

    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }

    this.animationFrameId = requestAnimationFrame(this.update.bind(this));
  }

  startLoop() {
    if (!this.active || this.paused || this.animationFrameId) return;
    this.lastTime = performance.now() * 0.001;
    this.update();
  }

  pause() {
    this.paused = true;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  resume() {
    if (!this.active) return;
    this.paused = false;
    this.startLoop();
  }

  destroy() {
    this.active = false;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    window.removeEventListener('resize', this._onResize);
    if (this.ro) {
      this.ro.disconnect();
      this.ro = null;
    }
    document.removeEventListener('mousemove', this._onPointerMove);
    document.removeEventListener('pointermove', this._onPointerMove);
    document.removeEventListener('mouseleave', this._onMouseLeave);

    if (this.mount && this.renderer && this.mount.contains(this.renderer.domElement)) {
      this.mount.removeChild(this.renderer.domElement);
    }
    if (this.geo) {
      this.geo.dispose();
      this.geo = null;
    }
    if (this.material) {
      this.material.dispose();
      this.material = null;
    }
    if (this.renderer) {
      this.renderer.dispose();
      if (typeof this.renderer.forceContextLoss === 'function') {
        this.renderer.forceContextLoss();
      }
      this.renderer = null;
    }
  }
}

/**
 * Vitalis AI Health Companion Interactive Controller
 */
(function(window) {
  'use strict';

  window.VitalisShapeBlur = VitalisShapeBlur;

  const VitalisCompanion = {
    isOpen: false,
    initialized: false,
    _lastToggle: 0,
    shapeBlur: null,

    init() {
      if (this.initialized) return;

      const root = document.getElementById('vitalis-companion-root');
      const launcher = document.getElementById('vitalis-companion-launcher');
      const panel = document.getElementById('vitalis-companion-panel');
      const wrapper = document.getElementById('vitalis-companion-launcher-wrapper');
      if (!root || !launcher || !panel) return;

      this.initialized = true;

      // Initialize localized Three.js WebGL ShapeBlur interaction (Pure Circular)
      const mount = document.getElementById('vitalis-shapeblur-mount');
      if (mount && !this.shapeBlur && typeof VitalisShapeBlur !== 'undefined') {
        this.shapeBlur = new VitalisShapeBlur(mount, {
          variation: 2,
          pixelRatioProp: 2,
          shapeSize: 0.48,
          roundness: 0.5,
          borderSize: 0.045,
          circleSize: 0.35,
          circleEdge: 0.52,
          color: '#06b6d4',
          color2: '#8b5cf6'
        });
      }

      // Automatically open companion when redirected with ?open_companion=1
      try {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('open_companion') === '1') {
          setTimeout(() => {
            this.open();
            if (window.history && window.history.replaceState) {
              window.history.replaceState({}, document.title, window.location.pathname);
            }
          }, 250);
        }
      } catch (e) {
        /* Ignore query parsing errors */
      }

      // Detect and apply page context
      const endpoint = ((root.dataset && root.dataset.endpoint) || window.location.pathname || '').toLowerCase();
      const contextEl = document.getElementById('companion-context-text');
      if (contextEl) {
        if (endpoint.includes('dashboard') || endpoint === '/' || endpoint.endsWith('/dashboard')) {
          contextEl.textContent = "You're viewing your Wellness Dashboard";
        } else if (endpoint.includes('activity')) {
          contextEl.textContent = "You're viewing your Daily Activity records";
        } else if (endpoint.includes('recommendations')) {
          contextEl.textContent = "You're viewing your Personalized Recommendations";
        } else if (endpoint.includes('progress')) {
          contextEl.textContent = "You're viewing your Progress Trends & Analytics";
        } else if (endpoint.includes('weekly_report')) {
          contextEl.textContent = "You're viewing your Weekly Behavioral Report";
        } else if (endpoint.includes('profile')) {
          contextEl.textContent = "You're viewing your Health Profile & Biometrics";
        } else if (endpoint.includes('how_it_works')) {
          contextEl.textContent = "You're viewing How Vitalis AI Works";
        } else if (endpoint.includes('assistant')) {
          contextEl.textContent = "You're on the AI Assistant page";
        } else if (endpoint.includes('admin')) {
          contextEl.textContent = "You're viewing Admin ML Diagnostics";
        } else {
          contextEl.textContent = "Context: Personal Health Telemetry";
        }
      }

      // Click & keydown handlers
      const handleToggle = (e) => {
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        this.toggle();
      };

      launcher.onclick = handleToggle;
      if (wrapper) {
        wrapper.onclick = handleToggle;
        wrapper.onkeydown = (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            this.toggle();
          }
        };
      }

      launcher.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          e.stopPropagation();
          this.toggle();
        }
      };

      // Close & Minimize buttons
      const closeBtn = document.getElementById('btn-close-companion');
      if (closeBtn) {
        closeBtn.onclick = (e) => {
          if (e) {
            e.preventDefault();
            e.stopPropagation();
          }
          this.close();
        };
      }

      const minBtn = document.getElementById('btn-minimize-companion');
      if (minBtn) {
        minBtn.onclick = (e) => {
          if (e) {
            e.preventDefault();
            e.stopPropagation();
          }
          this.close();
        };
      }

      // Escape key closes panel
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });

      // Clicking outside closes panel
      document.addEventListener('click', (e) => {
        if (!this.isOpen) return;
        if (
          panel.contains(e.target) || 
          launcher.contains(e.target) || 
          (wrapper && wrapper.contains(e.target))
        ) {
          return;
        }
        this.close();
      });
    },

    open() {
      const launcher = document.getElementById('vitalis-companion-launcher');
      const panel = document.getElementById('vitalis-companion-panel');
      const wrapper = document.getElementById('vitalis-companion-launcher-wrapper');
      if (!panel) return;

      this.isOpen = true;
      panel.classList.add('open');
      panel.setAttribute('aria-hidden', 'false');
      if (wrapper) {
        wrapper.classList.add('panel-open');
      }
      if (launcher) {
        launcher.classList.add('panel-open');
        launcher.setAttribute('aria-expanded', 'true');
      }
      if (this.shapeBlur) {
        this.shapeBlur.pause();
      }

      const input = document.getElementById('companion-chat-input');
      if (input) {
        setTimeout(() => input.focus(), 160);
      }
    },

    close() {
      const launcher = document.getElementById('vitalis-companion-launcher');
      const panel = document.getElementById('vitalis-companion-panel');
      const wrapper = document.getElementById('vitalis-companion-launcher-wrapper');
      if (!panel) return;

      this.isOpen = false;
      panel.classList.remove('open');
      panel.setAttribute('aria-hidden', 'true');
      if (wrapper) {
        wrapper.classList.remove('panel-open');
      }
      if (launcher) {
        launcher.classList.remove('panel-open');
        launcher.setAttribute('aria-expanded', 'false');
        launcher.focus();
      }
      if (this.shapeBlur) {
        this.shapeBlur.resume();
      }
    },

    toggle() {
      const now = Date.now();
      if (now - this._lastToggle < 250) {
        return;
      }
      this._lastToggle = now;

      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    },

    destroy() {
      this.initialized = false;
      if (this.shapeBlur) {
        this.shapeBlur.destroy();
        this.shapeBlur = null;
      }
    },

    sendPrompt(text) {
      const input = document.getElementById('companion-chat-input');
      if (input) {
        input.value = text;
        this.handleSubmit();
      }
    },

    async handleSubmit(e) {
      if (e) e.preventDefault();
      const input = document.getElementById('companion-chat-input');
      const sendBtn = document.getElementById('btn-companion-send');
      if (!input) return;

      const msg = input.value.trim();
      if (!msg) return;

      this.appendMessage(msg, 'user');
      input.value = '';
      input.disabled = true;

      if (sendBtn && window.VitalisLoader) {
        VitalisLoader.setButtonLoading(sendBtn, true);
      }

      const loadingBubble = this.appendMessage('', 'assistant');
      loadingBubble.innerHTML = window.VitalisLoader 
        ? VitalisLoader.inlineHtml('vitalis-loader-sm')
        : '...';

      try {
        const res = await fetch('/api/assistant/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg })
        });
        const data = await res.json();
        loadingBubble.innerHTML = `
          <div>${data.reply}</div>
          ${data.disclaimer ? `<div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.4rem; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 0.3rem;">${data.disclaimer}</div>` : ''}
        `;
      } catch (err) {
        loadingBubble.textContent = "I encountered a network issue while retrieving your health records. Please try again.";
      } finally {
        if (sendBtn && window.VitalisLoader) {
          VitalisLoader.setButtonLoading(sendBtn, false);
        }
        input.disabled = false;
        input.focus();
        this.scrollToBottom();
      }
    },

    appendMessage(text, sender) {
      const container = document.getElementById('companion-messages-container');
      if (!container) return null;
      const bubble = document.createElement('div');
      bubble.className = `chat-bubble chat-${sender}`;
      if (text) bubble.textContent = text;
      container.appendChild(bubble);
      this.scrollToBottom();
      return bubble;
    },

    scrollToBottom() {
      const container = document.getElementById('companion-messages-container');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }
  };

  window.VitalisCompanion = VitalisCompanion;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => VitalisCompanion.init());
  } else {
    VitalisCompanion.init();
  }
})(window);

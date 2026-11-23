/**
 * NOVA AI AGENT - GENIE ANIMATION MATHEMATICAL ENGINE
 * Inspired by classic macOS Genie effect and fluid liquid SVG deformation.
 * Calculates dynamic Bézier paths connecting trigger origin to target panel.
 */

/**
 * Clamps value between min and max.
 */
export function clamp(val, min, max) {
  return Math.min(Math.max(val, min), max);
}

/**
 * Easing functions for leading and trailing edges of the genie stretch.
 */
export const eases = {
  // Snappy Apple cubic ease out
  easeOutCubic: (t) => 1 - Math.pow(1 - t, 3),
  // Smooth ease in
  easeInQuad: (t) => t * t,
  // S-curve smoothstep
  easeInOutCubic: (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
};

/**
 * Normalizes a DOMRect or object into { x, y, w, h }
 */
export function normalizeRect(rect) {
  if (!rect) {
    return { x: window.innerWidth / 2 - 20, y: window.innerHeight - 80, w: 40, h: 40 };
  }
  return {
    x: rect.x ?? rect.left ?? 0,
    y: rect.y ?? rect.top ?? 0,
    w: rect.width ?? rect.w ?? 40,
    h: rect.height ?? rect.h ?? 40,
  };
}

/**
 * Computes the fluid SVG path for the Genie Effect deformation at progress p (0 to 1).
 *
 * @param {Object} src - { x, y, w, h } Origin/trigger rectangle
 * @param {Object} dst - { x, y, w, h } Destination modal/dialog rectangle
 * @param {number} p - Animation progress 0.0 -> 1.0
 * @param {string} mode - 'auto' | 'bottom-up' | 'top-down' | 'side'
 * @returns {string} SVG path string
 */
export function computeGeniePath(srcRaw, dstRaw, p, mode = 'auto') {
  const src = normalizeRect(srcRaw);
  const dst = normalizeRect(dstRaw);

  const t = clamp(p, 0, 1);

  // When fully expanded (t >= 0.999), return exact target rectangle
  if (t >= 0.999) {
    const isFullscreen = dst.x === 0 && dst.y === 0 && Math.abs(dst.w - window.innerWidth) < 5;
    const r = isFullscreen ? 0 : 24; // Subtle Apple rounded corner approximation or straight rect
    return `M ${dst.x + r} ${dst.y} ` +
           `H ${dst.x + dst.w - r} ` +
           `Q ${dst.x + dst.w} ${dst.y} ${dst.x + dst.w} ${dst.y + r} ` +
           `V ${dst.y + dst.h - r} ` +
           `Q ${dst.x + dst.w} ${dst.y + dst.h} ${dst.x + dst.w - r} ${dst.y + dst.h} ` +
           `H ${dst.x + r} ` +
           `Q ${dst.x} ${dst.y + dst.h} ${dst.x} ${dst.y + dst.h - r} ` +
           `V ${dst.y + r} ` +
           `Q ${dst.x} ${dst.y} ${dst.x + r} ${dst.y} Z`;
  }

  // Determine direction
  let isBottomUp = mode === 'bottom-up';
  if (mode === 'auto') {
    isBottomUp = (src.y + src.h / 2) >= (dst.y + dst.h / 2);
  }

  // Liquid expansion: The leading edge travels faster than trailing edge
  // Creating the classic neck / hourglass stretch
  const tLead = 1 - Math.pow(1 - t, 2.4);
  const tTrail = Math.pow(t, 2.1);

  let yTop, yBot, wTop, wBot, cxTop, cxBot;

  if (isBottomUp) {
    // Top moves upward towards target first
    yTop = src.y + (dst.y - src.y) * tLead;
    // Bottom stays anchored longer near trigger
    yBot = (src.y + src.h) + ((dst.y + dst.h) - (src.y + src.h)) * tTrail;

    // Width flares open at top while staying constricted at bottom
    wTop = src.w + (dst.w - src.w) * tLead;
    wBot = src.w + (dst.w - src.w) * tTrail;

    // Centers interpolate smoothly
    const srcCx = src.x + src.w / 2;
    const dstCx = dst.x + dst.w / 2;
    cxTop = srcCx + (dstCx - srcCx) * tLead;
    cxBot = srcCx + (dstCx - srcCx) * tTrail;
  } else {
    // Top-down (e.g. dropdowns, header menus)
    yTop = src.y + (dst.y - src.y) * tTrail;
    yBot = (src.y + src.h) + ((dst.y + dst.h) - (src.y + src.h)) * tLead;

    wTop = src.w + (dst.w - src.w) * tTrail;
    wBot = src.w + (dst.w - src.w) * tLead;

    const srcCx = src.x + src.w / 2;
    const dstCx = dst.x + dst.w / 2;
    cxTop = srcCx + (dstCx - srcCx) * tTrail;
    cxBot = srcCx + (dstCx - srcCx) * tLead;
  }

  // Ensure positive height
  if (yBot <= yTop + 2) {
    yBot = yTop + 2;
  }

  const xTl = cxTop - wTop / 2;
  const xTr = cxTop + wTop / 2;
  const xBl = cxBot - wBot / 2;
  const xBr = cxBot + wBot / 2;

  const dy = Math.max(2, yBot - yTop);

  // Inflection curvature factor for the liquid waist
  // The curve bends inward when expanding and straightens as it reaches 1.0
  const curvature = (1 - t) * 0.18;

  // Left lateral cubic Bézier (from bottom-left up to top-left)
  const c1x = xBl + (xTl - xBl) * 0.12 - (wTop * curvature);
  const c1y = yBot - dy * 0.38;
  const c2x = xTl - (xTl - xBl) * 0.12 - (wTop * curvature * 0.5);
  const c2y = yTop + dy * 0.38;

  // Right lateral cubic Bézier (from top-right down to bottom-right)
  const c3x = xTr + (xBr - xTr) * 0.12 + (wTop * curvature * 0.5);
  const c3y = yTop + dy * 0.38;
  const c4x = xBr - (xBr - xTr) * 0.12 + (wTop * curvature);
  const c4y = yBot - dy * 0.38;

  // Build the continuous organic SVG path
  return `M ${xTl.toFixed(1)} ${yTop.toFixed(1)} ` +
         `L ${xTr.toFixed(1)} ${yTop.toFixed(1)} ` +
         `C ${c3x.toFixed(1)} ${c3y.toFixed(1)}, ${c4x.toFixed(1)} ${c4y.toFixed(1)}, ${xBr.toFixed(1)} ${yBot.toFixed(1)} ` +
         `L ${xBl.toFixed(1)} ${yBot.toFixed(1)} ` +
         `C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${xTl.toFixed(1)} ${yTop.toFixed(1)} Z`;
}

/**
 * Calculates CSS transform parameters (origin and scale) during the genie morph
 * to harmonize the clipped inner content with the outer liquid outline.
 */
export function computeGenieTransform(srcRaw, dstRaw, p) {
  const src = normalizeRect(srcRaw);
  const dst = normalizeRect(dstRaw);
  const t = clamp(p, 0, 1);

  const srcCx = src.x + src.w / 2;
  const srcCy = src.y + src.h / 2;

  // Origin relative to dst
  const originX = `${((srcCx - dst.x) / Math.max(1, dst.w)) * 100}%`;
  const originY = `${((srcCy - dst.y) / Math.max(1, dst.h)) * 100}%`;

  // Scale and opacity
  const scale = 0.85 + 0.15 * eases.easeOutCubic(t);
  const opacity = clamp(t * 2.2, 0, 1);

  return {
    transformOrigin: `${originX} ${originY}`,
    opacity,
    scale,
  };
}

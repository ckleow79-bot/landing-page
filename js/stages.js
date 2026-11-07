/**
 * Scroll "stages": a tall section whose inner panel sticks to the screen while
 * scroll progress (0 to 1) is written to --p on the section. CSS does the rest:
 *   .stage-frame  photo opens from a small rectangle to full bleed (Academy)
 *   .stage-iris   photo is revealed through a growing circle (Home)
 * Without GSAP, or with reduced motion, sections stay static with the photo shown.
 */
(function () {
    'use strict';
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;
    gsap.registerPlugin(ScrollTrigger);
    document.querySelectorAll('.stage-frame, .stage-iris').forEach(sec => {
        sec.classList.add('is-live');
        sec.style.setProperty('--p', '0');
        ScrollTrigger.create({
            trigger: sec, start: 'top top', end: 'bottom bottom',
            onUpdate: st => sec.style.setProperty('--p', st.progress.toFixed(4))
        });
    });
    ScrollTrigger.refresh();
})();

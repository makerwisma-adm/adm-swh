/**
 * Navbar brand: kosong → huruf muncul satu per satu → utuh → ulang.
 */
(function () {
    'use strict';

    const CHAR_MS = 78;
    const SPACE_MS = 32;
    const WORD_GAP_MS = 110;
    const START_PAUSE_MS = 420;
    const HOLD_MS = 3000;
    const FADE_OUT_MS = 280;

    function delayAfter(ch, nextIndex, text) {
        if (nextIndex >= text.length) return 0;
        if (ch === ' ') return SPACE_MS;
        if (nextIndex === 5 && text.startsWith('SPPG')) return CHAR_MS + WORD_GAP_MS;
        if (nextIndex === 11 && text.startsWith('SPPG Wisma')) return CHAR_MS + WORD_GAP_MS;
        return CHAR_MS;
    }

    function startTyping(root) {
        const text = root.dataset.text
            || root.querySelector('.nav-brand-typing__ghost')?.textContent
            || '';
        const live = root.querySelector('.nav-brand-typing__live');
        if (!live || !text) return;

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            live.textContent = text;
            live.removeAttribute('aria-hidden');
            return;
        }

        let index = 0;
        let timer = null;

        function clearTimer() {
            if (timer !== null) {
                clearTimeout(timer);
                timer = null;
            }
        }

        function beginCycle() {
            clearTimer();
            index = 0;
            live.textContent = '';
            live.style.opacity = '1';
            timer = setTimeout(typeNext, START_PAUSE_MS);
        }

        function endCycle() {
            live.style.opacity = '0';
            timer = setTimeout(beginCycle, FADE_OUT_MS);
        }

        function typeNext() {
            if (index >= text.length) {
                timer = setTimeout(endCycle, HOLD_MS);
                return;
            }

            live.textContent = text.slice(0, index + 1);
            const ch = text[index];
            index += 1;
            timer = setTimeout(typeNext, delayAfter(ch, index, text));
        }

        beginCycle();
    }

    function init() {
        document.querySelectorAll('.nav-brand-typing').forEach(startTyping);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
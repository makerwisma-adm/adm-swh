(function () {
    'use strict';

    function applyTheme(theme) {
        if (!theme) return;
        const root = document.documentElement;
        const map = {
            '--bgn-navy': theme.primary,
            '--bgn-blue': theme.secondary,
            '--bgn-gold': theme.accent,
            '--bgn-icon': theme.icon,
            '--theme-primary': theme.primary,
            '--theme-accent': theme.accent,
            '--theme-secondary': theme.secondary,
            '--icon-radius': theme.icon_radius || '12px',
        };
        Object.entries(map).forEach(([k, v]) => {
            if (v) root.style.setProperty(k, v);
        });
        root.dataset.themePreset = theme.preset || 'classic';
        root.dataset.iconStyle = theme.icon_style || 'rounded';
    }

    if (window.__APP_THEME__) {
        applyTheme(window.__APP_THEME__);
    }

    window.applyAppTheme = applyTheme;
})();
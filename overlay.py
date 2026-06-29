def draw_overlays(page):
    page.evaluate("""
    () => {
        // remove any old badges from a previous perceive
        document.querySelectorAll('.ai-overlay-badge').forEach(b => b.remove());

        // find every stamped element
        const stamped = document.querySelectorAll('[data-ai-index]');
        stamped.forEach(el => {
            const idx = el.getAttribute('data-ai-index');
            const rect = el.getBoundingClientRect();

            // skip things with no real position
            if (rect.width === 0 || rect.height === 0) return;

            const badge = document.createElement('div');
            badge.className = 'ai-overlay-badge';
            badge.textContent = idx;
            badge.style.position = 'fixed';
            badge.style.left = rect.left + 'px';
            badge.style.top = rect.top + 'px';
            badge.style.background = 'rgba(255, 0, 0, 0.7)';
            badge.style.color = 'white';
            badge.style.fontSize = '11px';
            badge.style.fontWeight = 'bold';
            badge.style.padding = '1px 4px';
            badge.style.zIndex = '999999';
            badge.style.pointerEvents = 'none';
            document.body.appendChild(badge);
        });
    }
    """)
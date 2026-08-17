import queue
click_queue = queue.Queue()


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
            badge.style.zIndex = '2147483647';
            badge.style.pointerEvents = 'none';
            
            document.body.appendChild(badge);
        });
    }
    """)

def install_listener(page):
    page.evaluate("""
        if (!window._overlayHandler) {
            window.capturedText = '';
            window._lastAction = null;
            window._lastClickedElement = null;

            window.elementInfo = function(el) {
                if (!el) return null;
                let id = el.id || '';
                const P = 'oj-searchselect-filter-';
                if (id.startsWith(P)) { id = id.slice(P.length); }
                let name = el.getAttribute('aria-label') || el.getAttribute('title') ||
                        el.getAttribute('placeholder') || '';
                if (!name) {
                    const img = el.querySelector('img');
                    if (img) name = img.getAttribute('alt') || img.getAttribute('title') || '';
                }
                if (!name) name = el.innerText || '';
                return {
                    id: id,
                    name: name,
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || ''
                };
            }

            window._overlayClickHandler = (e) => {
                const el = e.target.closest('[data-ai-index]');
                if (el && el.tagName.toLowerCase() !== 'select') {
                    const info = window.elementInfo(el);
                    window._lastClickedElement = info;
                    window.badgeClicked(info);
                }
            };
            document.addEventListener('click', window._overlayClickHandler, true);

            window._overlayChangeHandler = (e) => {
                const el = e.target.closest('[data-ai-index]');
                if (el && el.tagName.toLowerCase() === 'select') {
                    const info = window.elementInfo(el);
                    info.value = el.options[el.selectedIndex].text.trim();
                    window._lastAction = { kind: 'select', target: info };
                }
            };
            document.addEventListener('change', window._overlayChangeHandler, true);

            window._overlayHandler = (e) => {
                const k = e.key;
                if (k === 'Backspace') {
                    window.capturedText = window.capturedText.slice(0, -1);
                }
                else if (k === 'CapsLock') {
                    if (window.capturedText !== '') {
                        window._lastAction = { kind: 'seal', mode: 'replace', value: window.capturedText, target: window.elementInfo(document.activeElement) };
                        window.capturedText = '';
                    }
                }
                else if (k === 'Insert') {
                    if (window.capturedText !== '') {
                        window._lastAction = { kind: 'seal', mode: 'append', value: window.capturedText, target: window.elementInfo(document.activeElement) };
                        window.capturedText = '';
                    }
                }
                else if (k === 'Shift' || k === 'Control' || k === 'Alt' || k === 'Meta') {
                    // ignore bare modifier keys
                }
                else if (k.length === 1) {
                    if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                        window.capturedText += k;
                    }
                }
                else {
                    window._lastAction = { kind: 'press', value: k };
                }
            };
            document.addEventListener('keydown', window._overlayHandler);
        }
    """)
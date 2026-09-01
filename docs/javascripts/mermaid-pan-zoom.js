document.addEventListener("DOMContentLoaded", function () {
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1 && node.tagName.toLowerCase() === 'svg' && node.closest('.mermaid')) {
                    initPanZoom(node);
                } else if (node.nodeType === 1 && node.classList && node.classList.contains('mermaid')) {
                    const svg = node.querySelector('svg');
                    if (svg) initPanZoom(svg);
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Also check for any already rendered
    document.querySelectorAll('.mermaid svg').forEach(initPanZoom);

    function initPanZoom(svg) {
        if (svg.dataset.panZoomInitialized) return;
        svg.dataset.panZoomInitialized = "true";

        // Style the container so it doesn't bleed over the TOC
        const container = svg.closest('.mermaid');
        if (container) {
            container.style.maxWidth = '100%';
            container.style.overflow = 'hidden';
            container.style.cursor = 'grab';
            container.style.border = '1px solid var(--md-code-bg-color)'; // optional nice touch
            container.style.borderRadius = '0.2rem';
        }

        let isDragging = false;
        let startX, startY;
        let viewBox = svg.viewBox.baseVal;

        // If viewBox is not set, we can't easily pan/zoom natively using this method
        if (!viewBox || viewBox.width === 0) {
            const w = svg.getAttribute('width') || svg.getBoundingClientRect().width;
            const h = svg.getAttribute('height') || svg.getBoundingClientRect().height;
            svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
            viewBox = svg.viewBox.baseVal;
        }

        let vbX = viewBox.x;
        let vbY = viewBox.y;
        let vbW = viewBox.width;
        let vbH = viewBox.height;

        svg.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            if (container) container.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();

            // Calculate movement
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            // Scale movement based on zoom level
            const scaleX = vbW / svg.clientWidth;
            const scaleY = vbH / svg.clientHeight;

            vbX -= dx * scaleX;
            vbY -= dy * scaleY;

            svg.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);

            startX = e.clientX;
            startY = e.clientY;
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
            if (container) container.style.cursor = 'grab';
        });

        // Zoom on wheel
        svg.addEventListener('wheel', (e) => {
            e.preventDefault();

            const zoomFactor = 1.1;
            const direction = e.deltaY > 0 ? 1 : -1;
            const factor = direction > 0 ? zoomFactor : 1 / zoomFactor;

            // Get mouse position relative to SVG
            const rect = svg.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Calculate SVG coordinates of the mouse
            const svgMouseX = vbX + (mouseX / rect.width) * vbW;
            const svgMouseY = vbY + (mouseY / rect.height) * vbH;

            // New viewBox dimensions
            const newVbW = vbW * factor;
            const newVbH = vbH * factor;

            // Adjust x and y so the point under the mouse remains stationary
            vbX = svgMouseX - (mouseX / rect.width) * newVbW;
            vbY = svgMouseY - (mouseY / rect.height) * newVbH;
            vbW = newVbW;
            vbH = newVbH;

            svg.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
        }, { passive: false });
    }
});

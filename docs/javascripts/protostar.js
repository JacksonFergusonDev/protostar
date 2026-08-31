(() => {
    function enhanceCopyButtons(root = document) {
        root.querySelectorAll("[data-copy]").forEach((button) => {
            // Prevent double-binding
            if (button.dataset.psReady === "true") return;
            button.dataset.psReady = "true";

            const idleLabel = button.textContent;

            button.addEventListener("click", async () => {
                const text = button.dataset.copy || "";
                try {
                    await navigator.clipboard.writeText(text);
                    button.textContent = "Copied!";
                } catch {
                    button.textContent = "Failed";
                }

                // Revert back to original text after 1.8 seconds
                window.setTimeout(() => {
                    button.textContent = idleLabel;
                }, 1800);
            });
        });
    }

    // Initialize on direct page loads
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => enhanceCopyButtons(), { once: true });
    } else {
        enhanceCopyButtons();
    }

    // Initialize on Zensical/MkDocs instant navigation transitions
    if (typeof window.document$ !== "undefined") {
        window.document$.subscribe(() => enhanceCopyButtons());
    }
})();

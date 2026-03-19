// SPDX-FileCopyrightText: 2026 Jiri Vyskocil
// SPDX-License-Identifier: Apache-2.0

/**
 * Adds an "Enlarge" button to each rendered Mermaid diagram.
 * Clicking it opens the diagram in a fullscreen overlay (lightbox-style).
 * Close via backdrop click, the X button, or Escape.
 */
;(() => {
  const BUTTON_LABEL = "\u2922 Enlarge"

  /** Build the overlay element (singleton, appended on first use). */
  function createOverlay() {
    const overlay = document.createElement("div")
    overlay.className = "mermaid-zoom-overlay"
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeOverlay(overlay)
    })

    const close = document.createElement("button")
    close.className = "mermaid-zoom-close"
    close.textContent = "\u2715"
    close.title = "Close"
    close.addEventListener("click", () => closeOverlay(overlay))

    const viewport = document.createElement("div")
    viewport.className = "mermaid-zoom-viewport"

    overlay.append(close, viewport)
    document.body.appendChild(overlay)
    return overlay
  }

  function openOverlay(svgSource) {
    const overlay =
      document.querySelector(".mermaid-zoom-overlay") || createOverlay()
    const viewport = overlay.querySelector(".mermaid-zoom-viewport")
    viewport.innerHTML = ""
    const clone = svgSource.cloneNode(true)
    clone.removeAttribute("height")
    clone.removeAttribute("width")
    clone.style.maxWidth = "100%"
    clone.style.maxHeight = "100%"
    clone.style.width = "auto"
    clone.style.height = "auto"
    viewport.appendChild(clone)
    overlay.classList.add("mermaid-zoom-active")
    document.addEventListener("keydown", onEscape)
  }

  function closeOverlay(overlay) {
    overlay.classList.remove("mermaid-zoom-active")
    document.removeEventListener("keydown", onEscape)
  }

  function onEscape(e) {
    if (e.key === "Escape") {
      const overlay = document.querySelector(".mermaid-zoom-overlay")
      if (overlay) closeOverlay(overlay)
    }
  }

  /** Wrap a rendered mermaid container and inject the enlarge button. */
  function attachButton(container) {
    if (container.dataset.zoomAttached) return
    container.dataset.zoomAttached = "1"

    const wrapper = document.createElement("div")
    wrapper.className = "mermaid-zoom-wrapper"
    container.parentNode.insertBefore(wrapper, container)
    wrapper.appendChild(container)

    const btn = document.createElement("button")
    btn.className = "mermaid-zoom-btn"
    btn.textContent = BUTTON_LABEL
    btn.addEventListener("click", () => {
      const svg = container.querySelector("svg") || container
      openOverlay(svg.closest("svg") ? svg : svg.querySelector("svg") || svg)
    })
    container.before(btn)
  }

  /** Scan the DOM for rendered mermaid SVGs and attach buttons. */
  function scan() {
    document.querySelectorAll("pre.mermaid, .mermaid").forEach((el) => {
      if (el.querySelector("svg") || el.tagName === "SVG") attachButton(el)
    })
  }

  // Initial scan once DOM + mermaid rendering settle.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(scan, 500))
  } else {
    setTimeout(scan, 500)
  }

  // Catch diagrams rendered after initial load (e.g. instant navigation).
  new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== 1) continue
        if (
          (node.matches?.(".mermaid, pre.mermaid") && node.querySelector("svg")) ||
          node.querySelector?.(".mermaid svg, pre.mermaid svg")
        ) {
          setTimeout(scan, 200)
          return
        }
      }
    }
  }).observe(document.body, { childList: true, subtree: true })
})()

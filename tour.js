/* Smokeshed guided tour: plain JavaScript, no library, no build step.

   TO EDIT THE TOUR, CHANGE ONLY THIS ARRAY.
   Each step points at an element marked data-tour="..." in index.html.
   Keep each text to 1-2 short sentences. Steps whose element is missing or
   hidden (e.g. the Singapore box when another place is chosen) are skipped.

   Tip for demos: index.html?tour=4 opens the tour at step 4. */
const TOUR_STEPS = [
  { target: '[data-tour="place"]', title: "Pick a place",
    text: "Search for a city, tap one under “Try”, or click anywhere on the map. The whole page updates for that place." },
  { target: '[data-tour="status"]', title: "Is it burning more than normal?",
    text: "Fires seen by NASA satellites in the last 7 days, compared with a normal week for this month since 2001: Quiet, Normal, Above normal or Surge." },
  { target: '[data-tour="singapore"]', title: "Singapore haze warning",
    text: "When fires surge in Sumatra, Singapore's air has got worse about 1 day later (“~1 day”). Below it: Singapore's air quality right now." },
  { target: '[data-tour="map"]', title: "The map",
    text: "Dots are fires from the last 7 days: darker = more, faded = not burning in the last 2 days. Grey arrows show where the wind is carrying smoke right now." },
  { target: '[data-tour="calendar"]', title: "The burning calendar",
    text: "Each square is one month since 2001; darker means more fires. Hover a square for the exact number." },
  { target: '[data-tour="csv"]', title: "Take the data with you",
    text: "Download the months shown as a CSV file for a report or spreadsheet." },
];

(function () {
  "use strict";

  // ---------- remembering "seen" (never crash if storage is blocked) ----------
  const KEY = "smokeshed-tour-seen";
  function markSeen() { try { localStorage.setItem(KEY, "1"); } catch (e) { /* storage off: banner shows again next time */ } }
  function wasSeen() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }

  const NARROW = 600;  // below this width the popup becomes a bottom sheet
  const isNarrow = () => window.innerWidth < NARROW;

  // ---------- styles (use the page's colour tokens, so dark mode just works) ----------
  const css = document.createElement("style");
  css.textContent = `
    .tour-hl { position: fixed; z-index: 1001; pointer-events: none; border-radius: 10px;
               outline: 3px solid var(--accent); outline-offset: 0;
               box-shadow: 0 0 0 9999px rgba(0,0,0,.35); transition: all .15s ease; }
    .tour-hl-tag { position: absolute; left: -3px; top: -26px; background: var(--accent); color: #fff;
                   font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 6px; white-space: nowrap; }
    .tour-hl.tag-inside .tour-hl-tag { top: 6px; left: 6px; }
    .tour-pop { position: fixed; z-index: 1002; width: 320px; max-width: calc(100vw - 32px);
                background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 10px;
                box-shadow: 0 8px 28px rgba(0,0,0,.28); padding: 14px 16px; }
    .tour-pop:focus { outline: none; }
    .tour-pop:focus-visible { outline: 2px solid var(--accent); }
    .tour-pop.sheet { left: 0 !important; right: 0; bottom: 0; top: auto !important; width: auto; max-width: none;
                      border-radius: 14px 14px 0 0; padding-bottom: 18px; }
    .tour-count { margin: 0; font-size: 12px; color: var(--ink-2); }
    .tour-pop h3 { margin: 2px 0 6px; font-size: 16px; }
    .tour-pop p.tour-text { margin: 0 0 12px; font-size: 14px; line-height: 1.45; }
    .tour-btns { display: flex; gap: 6px; align-items: center; }
    .tour-btns .tour-skip { border: 0; background: none; color: var(--ink-2); padding: 6px 4px; text-decoration: underline; }
    .tour-btns .tour-space { flex: 1; }
    .tour-btns button:disabled { opacity: .4; cursor: default; }
    .tour-banner { position: fixed; z-index: 1000; right: 16px; bottom: 16px; display: flex; align-items: center; gap: 8px;
                   background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 10px;
                   box-shadow: 0 6px 20px rgba(0,0,0,.2); padding: 8px 8px 8px 14px; font-size: 14px; }
    .tour-banner .tour-x { border: 0; background: none; font-size: 18px; line-height: 1; padding: 4px 8px; color: var(--ink-2); }
    @media (max-width: ${NARROW - 1}px) { .tour-banner { left: 8px; right: 8px; bottom: 8px; } .tour-banner span { flex: 1; } }
    .tour-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  `;
  document.head.appendChild(css);

  // ---------- building blocks ----------
  function make(tag, attrs, html) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
    if (html) el.innerHTML = html;
    return el;
  }

  const live = make("div", { class: "tour-sr", "aria-live": "polite" });  // announces step changes
  document.body.appendChild(live);

  const highlight = make("div", { class: "tour-hl", "aria-hidden": "true" }, '<span class="tour-hl-tag"></span>');
  const popup = make("div", { class: "tour-pop", role: "dialog", "aria-labelledby": "tour-title",
                              "aria-describedby": "tour-text", tabindex: "-1" },
    `<p class="tour-count" id="tour-count"></p>
     <h3 id="tour-title"></h3>
     <p class="tour-text" id="tour-text"></p>
     <div class="tour-btns">
       <button type="button" class="tour-skip">Skip tour</button>
       <span class="tour-space"></span>
       <button type="button" class="tour-back">Back</button>
       <button type="button" class="tour-next primary">Next</button>
     </div>`);
  const backBtn = popup.querySelector(".tour-back");
  const nextBtn = popup.querySelector(".tour-next");

  const banner = make("div", { class: "tour-banner", role: "region", "aria-label": "Guided tour" },
    `<span>New here? Take the 30-second tour.</span>
     <button type="button" class="primary tour-start">Start</button>
     <button type="button" class="tour-x" aria-label="Dismiss the tour suggestion">×</button>`);

  // ---------- the tour ----------
  let steps = [];        // the steps whose targets exist right now
  let current = 0;
  let returnFocus = null;

  // The step's element, or null if it's missing or hidden (then the step is skipped).
  function targetOf(step) {
    const el = document.querySelector(step.target);
    return el && !el.closest("[hidden]") && el.getClientRects().length > 0 ? el : null;
  }

  function start(at) {
    hideBanner();
    markSeen();
    steps = TOUR_STEPS.filter(targetOf);
    if (!steps.length) return;
    if (!popup.isConnected) {
      returnFocus = document.activeElement;
      document.body.append(highlight, popup);
      document.addEventListener("keydown", onKey);
      window.addEventListener("resize", position);
      window.addEventListener("scroll", position, true);  // true: also when the answer panel scrolls
    }
    show(Math.max(0, Math.min(at || 0, steps.length - 1)));
  }

  function show(n) {
    current = n;
    const step = steps[current];
    const target = targetOf(step);
    if (!target) {  // it disappeared since the tour started: drop it and carry on
      steps.splice(current, 1);
      return steps.length ? show(Math.min(current, steps.length - 1)) : end();
    }
    const label = `Step ${current + 1} of ${steps.length}`;
    popup.querySelector("#tour-count").textContent = label;
    popup.querySelector("#tour-title").textContent = step.title;
    popup.querySelector("#tour-text").textContent = step.text;
    highlight.firstChild.textContent = `${label}: ${step.title}`;
    backBtn.disabled = current === 0;
    nextBtn.textContent = current === steps.length - 1 ? "Done" : "Next";
    live.textContent = `${label}. ${step.title}. ${step.text}`;

    // Centre the target, unless it's taller than the screen: then show its top,
    // so people see where it begins, not its middle.
    const tall = target.getBoundingClientRect().height > window.innerHeight * 0.75;
    target.scrollIntoView({ block: isNarrow() || tall ? "start" : "center", behavior: "instant" });
    position();
    popup.focus({ preventScroll: true });
  }

  // Put the highlight on the target and the popup beside it (or a bottom sheet on phones).
  function position() {
    if (!popup.isConnected) return;
    const target = targetOf(steps[current]);
    if (!target) return;
    const r = target.getBoundingClientRect();
    const pad = 6, vw = window.innerWidth, vh = window.innerHeight;
    Object.assign(highlight.style, {
      left: `${r.left - pad}px`, top: `${r.top - pad}px`,
      width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px`,
    });
    highlight.classList.toggle("tag-inside", r.top < 34);

    if (isNarrow()) { popup.classList.add("sheet"); return; }
    popup.classList.remove("sheet");

    const pw = popup.offsetWidth, ph = popup.offsetHeight, gap = 16, m = 8;
    const clampY = y => Math.max(m, Math.min(y, vh - ph - m));
    const clampX = x => Math.max(m, Math.min(x, vw - pw - m));
    const options = [
      [r.right + gap, clampY(r.top)],          // right of the target
      [r.left - gap - pw, clampY(r.top)],      // left
      [clampX(r.left), r.bottom + gap],        // below
      [clampX(r.left), r.top - gap - ph],      // above
    ];
    const fits = ([x, y]) => x >= m && y >= m && x + pw <= vw - m && y + ph <= vh - m;
    // Nothing fits (a huge target): sit inside its bottom-right corner.
    const [x, y] = options.find(fits)
      || [clampX(Math.min(r.right, vw) - pw - 12), clampY(Math.min(r.bottom, vh) - ph - 12)];
    popup.style.left = `${x}px`;
    popup.style.top = `${y}px`;
  }

  function next() { current < steps.length - 1 ? show(current + 1) : end(); }
  function back() { if (current > 0) show(current - 1); }

  function end() {
    highlight.remove();
    popup.remove();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", position);
    window.removeEventListener("scroll", position, true);
    live.textContent = "Tour closed.";
    if (returnFocus && typeof returnFocus.focus === "function") returnFocus.focus();
  }

  function onKey(e) {
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement && document.activeElement.tagName)) return;
    if (e.key === "Escape") { e.preventDefault(); end(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); next(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); back(); }
  }

  nextBtn.addEventListener("click", next);
  backBtn.addEventListener("click", back);
  popup.querySelector(".tour-skip").addEventListener("click", end);

  // ---------- the gentle invitation, and the "?" button ----------
  function hideBanner() { banner.remove(); }
  banner.querySelector(".tour-start").addEventListener("click", () => start(0));
  banner.querySelector(".tour-x").addEventListener("click", () => { markSeen(); hideBanner(); });

  const help = document.getElementById("tour-help");
  if (help) help.addEventListener("click", () => start(0));

  function onReady() {
    const asked = new URLSearchParams(window.location.search).get("tour");
    if (asked) start(Number(asked) - 1);         // e.g. ?tour=4 for demos
    else if (!wasSeen()) document.body.appendChild(banner);
  }
  if (window.smokeshedReady) onReady();
  else document.addEventListener("smokeshed:ready", onReady, { once: true });
})();

// Sweep now, filters, copy buttons, and the two actions. Everything else renders on the server.
(function () {
  const post = (url) => fetch(url, { method: "POST", headers: { "X-Undertaker": "1" } })
    .then((r) => r.json().then((j) => ({ ok: r.ok, body: j })));

  function toast(text) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2600);
  }

  const swept = document.getElementById("swept");
  function tick() {
    if (!swept || !swept.dataset.at) return;
    const s = Math.max(0, Math.round((Date.now() - Date.parse(swept.dataset.at)) / 1000));
    swept.textContent = "swept " + (s < 60 ? s + " s" : Math.floor(s / 60) + " min") + " ago";
  }
  tick();
  setInterval(tick, 1000);

  const sweep = document.getElementById("sweep");
  if (sweep) sweep.addEventListener("click", () => {
    sweep.disabled = true;
    sweep.textContent = "Sweeping…";
    post("/api/sweep").then(() => location.reload()).catch(() => {
      sweep.disabled = false;
      sweep.textContent = "Sweep now";
      toast("Sweep failed.");
    });
  });

  const filters = document.getElementById("filters");
  if (filters) filters.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const cause = chip.dataset.cause;
    filters.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === chip));
    document.querySelectorAll(".toetag").forEach((t) => {
      t.classList.toggle("hidden", cause !== "all" && t.dataset.cause !== cause);
    });
    history.replaceState(null, "", cause === "all" ? "/" : "/?cause=" + cause);
  });
  const want = new URLSearchParams(location.search).get("cause");
  if (want && filters) {
    const chip = filters.querySelector('.chip[data-cause="' + want + '"]');
    if (chip) chip.click();
  }

  document.querySelectorAll(".copy").forEach((b) => b.addEventListener("click", () => {
    navigator.clipboard.writeText(b.dataset.copy).then(
      () => { const old = b.textContent; b.textContent = "Copied"; setTimeout(() => (b.textContent = old), 1400); },
      () => toast("Copy failed; select the command instead."));
  }));

  const cert = document.querySelector(".cert");
  document.querySelectorAll(".action").forEach((b) => b.addEventListener("click", () => {
    if (b.disabled || !cert) return;
    if (!window.confirm(b.dataset.confirm)) return;
    const wid = encodeURIComponent(cert.dataset.wid);
    b.disabled = true;
    post("/api/w/" + wid + "/" + b.dataset.action).then(({ ok, body }) => {
      toast(body.message || (ok ? "Done." : "Failed."));
      if (ok) setTimeout(() => (location.href = b.dataset.action === "reset" ? location.href : "/"), 1200);
      else b.disabled = false;
    });
  }));
})();

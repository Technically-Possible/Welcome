document.addEventListener("DOMContentLoaded", async () => {
  const gallery = document.getElementById("gallery");
  const filtersHost = document.getElementById("filters");

  // Base for resolving assets when gallery page is /gallery/index.html
  const BASE = new URL("../", window.location.href);

  function resolveAssetPath(p) {
    const raw = String(p || "").replace(/\\/g, "/");
    if (!raw) return "";
    const cleaned = raw.startsWith("/") ? raw.slice(1) : raw; // avoid domain-root absolute
    return new URL(cleaned, BASE).href;
  }

  // Lightbox state (rebuilt when filters change)
  let currentLightboxList = []; // array of full image URLs (absolute)
  let currentIndex = 0;

  // Filter state
  const state = {
    year: "",
    city: "",
    tags: new Set(),   // semantic tags only
    tagMode: "any"     // "any" or "all"
  };

  // --------------------------
  // Helpers
  // --------------------------
  const norm = (s) => String(s || "").trim().toLowerCase();

  function inferYearCityFromPath(path) {
    // matches photography/<year>/<city>/...
    const p = String(path || "").replace(/\\/g, "/");
    const m = p.match(/photography\/(\d{4})\/([^\/]+)/i);
    if (!m) return { year: "", city: "" };
    return {
      year: m[1],
      city: decodeURIComponent(m[2]).replace(/_/g, " ")
    };
  }

  function uniqSorted(arr) {
    return Array.from(new Set(arr)).sort((a, b) => a.localeCompare(b));
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async function fetchJsonWithFallback() {
    // Works for domain root, subfolders, local server
    const candidates = [
      new URL("../photography.json", window.location.href).href,
      "/photography.json",
      "../photography.json",
      "photography.json"
    ];
    let lastErr = null;

    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
        return await res.json();
      } catch (e) {
        lastErr = e;
      }
    }
    throw lastErr || new Error("Failed to load photography.json");
  }

  // --------------------------
  // Load + normalize all images into a flat list
  // --------------------------
  let flat = [];
  try {
    const data = await fetchJsonWithFallback();

    // Expected: { years: [{year:"2025", events:[{name:"brighton", images:[{thumb,full,tags?}, ...]}]}]}
    const years = Array.isArray(data?.years) ? data.years : [];

    // Sort years descending
    years.sort((a, b) => String(b.year).localeCompare(String(a.year)));

    for (const y of years) {
      const yearStr = String(y.year || "");
      const events = Array.isArray(y.events) ? y.events : [];

      for (const ev of events) {
        const eventName = String(ev.name || "");
        const images = Array.isArray(ev.images) ? ev.images : [];

        for (const img of images) {
          const thumb = img.thumb;
          const full = img.full;

          const inferred = inferYearCityFromPath(full || thumb || "");
          const year = inferred.year || yearStr || "";
          const city = inferred.city || eventName || "";

          const semanticTags = Array.isArray(img.tags)
            ? img.tags.map(norm).filter(Boolean)
            : [];

          flat.push({
            year,
            city,
            thumb,
            full,
            semanticTags,
            thumbUrl: resolveAssetPath(thumb),
            fullUrl: resolveAssetPath(full)
          });
        }
      }
    }

    // Stable ordering
    

  } catch (error) {
    console.error("Error loading photography data", error);
    gallery.innerHTML = `<p>Failed to load photography.json. Check DevTools Console.</p>`;
    return;
  }

  // --------------------------
  // Mobile taskbar support
  // --------------------------
  function initMobileTaskbar(years, cities, tags) {
    const bar = document.getElementById("mobile-taskbar");
    if (!bar) return;

    const mYear = document.getElementById("mYearSelect");
    const mCity = document.getElementById("mCitySelect");
    const mTagsBtn = document.getElementById("mTagsBtn");
    const mTagsPanel = document.getElementById("mTagsPanel");
    const mClear = document.getElementById("mClearBtn");

    if (!mYear || !mCity || !mTagsBtn || !mTagsPanel || !mClear) return;

    mYear.innerHTML =
      `<option value="">Year</option>` +
      years.map(y => `<option value="${escapeHtml(y)}">${escapeHtml(y)}</option>`).join("");

    mCity.innerHTML =
      `<option value="">City</option>` +
      cities.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");

    mTagsPanel.innerHTML = tags.map(t => `
      <div class="mTagRow" data-tag="${escapeHtml(t)}">
        <input type="checkbox" ${state.tags.has(t) ? "checked" : ""}/>
        <span>${escapeHtml(t)}</span>
      </div>
    `).join("");

    // Toggle tags panel
    mTagsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      mTagsPanel.hidden = !mTagsPanel.hidden;
    });

    // Close panel if click outside
    document.addEventListener("click", () => {
      mTagsPanel.hidden = true;
    });

    mTagsPanel.addEventListener("click", (e) => {
      e.stopPropagation();
    });

    // Clicking a row toggles
    mTagsPanel.querySelectorAll(".mTagRow").forEach(row => {
      const cb = row.querySelector("input");
      const tag = row.dataset.tag;

      row.addEventListener("click", (e) => {
        if (e.target !== cb) cb.checked = !cb.checked;
        if (cb.checked) state.tags.add(tag);
        else state.tags.delete(tag);
        syncDesktopFromState();
        render();
      });
    });

    mYear.addEventListener("change", () => {
      state.year = mYear.value;
      syncDesktopFromState();
      render();
    });

    mCity.addEventListener("change", () => {
      state.city = mCity.value;
      syncDesktopFromState();
      render();
    });

    mClear.addEventListener("click", () => {
      state.year = "";
      state.city = "";
      state.tags.clear();
      state.tagMode = "any";
      syncDesktopFromState();
      syncMobileFromState();
      render();
    });

    syncMobileFromState();
  }

  function syncMobileFromState() {
    const mYear = document.getElementById("mYearSelect");
    const mCity = document.getElementById("mCitySelect");
    const mTagsPanel = document.getElementById("mTagsPanel");

    if (mYear) mYear.value = state.year || "";
    if (mCity) mCity.value = state.city || "";

    if (mTagsPanel) {
      mTagsPanel.querySelectorAll(".mTagRow").forEach(row => {
        const cb = row.querySelector("input");
        cb.checked = state.tags.has(row.dataset.tag);
      });
    }
  }

  function syncDesktopFromState() {
    const yearSelect = document.getElementById("yearSelect");
    const citySelect = document.getElementById("citySelect");
    const tagList = document.getElementById("tagList");

    if (yearSelect) yearSelect.value = state.year || "";
    if (citySelect) citySelect.value = state.city || "";

    if (tagList) {
      tagList.querySelectorAll(".tag-item").forEach(row => {
        const cb = row.querySelector("input");
        cb.checked = state.tags.has(row.dataset.tag);
      });
    }

    const anyRadio = document.querySelector("input[name='tagMode'][value='any']");
    const allRadio = document.querySelector("input[name='tagMode'][value='all']");
    if (anyRadio && allRadio) {
      if (state.tagMode === "all") allRadio.checked = true;
      else anyRadio.checked = true;
    }
  }

  // --------------------------
  // Build filter UI (Year / City / Tags dropdown)
  // --------------------------
  function buildFilters() {
    if (!filtersHost) return;

    const years = uniqSorted(flat.map(p => p.year).filter(Boolean)).sort((a, b) => b.localeCompare(a));
    const cities = uniqSorted(flat.map(p => p.city).filter(Boolean));
    const tags = uniqSorted(flat.flatMap(p => p.semanticTags).filter(Boolean));

    filtersHost.innerHTML = `
      <div class="filter-section">
        <h2>Year</h2>
        <select id="yearSelect" style="width:100%">
          <option value="">All years</option>
          ${years.map(y => `<option value="${escapeHtml(y)}">${escapeHtml(y)}</option>`).join("")}
        </select>
      </div>

      <div class="filter-section">
        <h2>City</h2>
        <select id="citySelect" style="width:100%">
          <option value="">All cities</option>
          ${cities.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("")}
        </select>
      </div>

      <div class="filter-section">
        <h2>Tags</h2>

        <div class="tag-controls">
          <button class="tag-btn" id="clearTagsBtn" type="button">Clear tags</button>
          <button class="tag-btn" id="clearAllBtn" type="button">Clear all</button>
        </div>

        <div class="tag-mode">
          <label><input type="radio" name="tagMode" value="any" checked> Match ANY selected tag</label>
          <label><input type="radio" name="tagMode" value="all"> Match ALL selected tags</label>
        </div>

        <details class="tag-dropdown" ${tags.length ? "" : "open"}>
          <summary style="cursor:pointer; font-family:'Press Start 2P', monospace; font-size:12px;">
            Select tags (${tags.length})
          </summary>
          <div class="filter-list tag-list" id="tagList"></div>
        </details>

        <div class="tag-empty" id="tagEmpty" style="display:${tags.length ? "none" : "block"};">
          No tags found yet. Run the auto-tag script to add tags into photography.json.
        </div>
      </div>
    `;

    // Wire events
    const yearSelect = document.getElementById("yearSelect");
    const citySelect = document.getElementById("citySelect");
    const tagList = document.getElementById("tagList");
    const clearTagsBtn = document.getElementById("clearTagsBtn");
    const clearAllBtn = document.getElementById("clearAllBtn");

    // Populate tags
    tagList.innerHTML = tags.map(t => `
      <div class="tag-item" data-tag="${escapeHtml(t)}">
        <input type="checkbox" ${state.tags.has(t) ? "checked" : ""}/>
        <span>${escapeHtml(t)}</span>
        <span class="tag-count"></span>
      </div>
    `).join("");

    tagList.querySelectorAll(".tag-item").forEach(row => {
      const cb = row.querySelector("input[type='checkbox']");
      const tag = row.dataset.tag;

      row.addEventListener("click", (e) => {
        if (e.target !== cb) cb.checked = !cb.checked;
        if (cb.checked) state.tags.add(tag);
        else state.tags.delete(tag);
        syncMobileFromState();
        render();
      });
    });

    yearSelect.addEventListener("change", () => {
      state.year = yearSelect.value;
      syncMobileFromState();
      render();
    });

    citySelect.addEventListener("change", () => {
      state.city = citySelect.value;
      syncMobileFromState();
      render();
    });

    document.querySelectorAll("input[name='tagMode']").forEach(radio => {
      radio.addEventListener("change", () => {
        state.tagMode = document.querySelector("input[name='tagMode']:checked").value;
        syncMobileFromState();
        render();
      });
    });

    clearTagsBtn.addEventListener("click", () => {
      state.tags.clear();
      tagList.querySelectorAll("input[type='checkbox']").forEach(cb => cb.checked = false);
      syncMobileFromState();
      render();
    });

    clearAllBtn.addEventListener("click", () => {
      state.year = "";
      state.city = "";
      state.tags.clear();
      state.tagMode = "any";
      yearSelect.value = "";
      citySelect.value = "";
      tagList.querySelectorAll("input[type='checkbox']").forEach(cb => cb.checked = false);
      const anyRadio = document.querySelector("input[name='tagMode'][value='any']");
      if (anyRadio) anyRadio.checked = true;
      syncMobileFromState();
      render();
    });

    // If the mobile taskbar exists on the page, initialise it
    initMobileTaskbar(years, cities, tags);
  }

  // --------------------------
  // Filtering + render
  // --------------------------
  function matches(p) {
    if (state.year && p.year !== state.year) return false;
    if (state.city && p.city !== state.city) return false;

    const chosen = Array.from(state.tags);
    if (chosen.length === 0) return true;

    const tagSet = new Set(p.semanticTags);
    if (state.tagMode === "any") {
      return chosen.some(t => tagSet.has(t));
    }
    // "all"
    return chosen.every(t => tagSet.has(t));
  }

  function render() {
    const filtered = flat.filter(matches);

    // ✅ Use resolved URLs (works in subfolders / GitHub Pages)
    currentLightboxList = filtered.map(p => p.fullUrl);

    gallery.innerHTML = "";

    if (filtered.length === 0) {
      gallery.innerHTML = `<p>No images match your filters.</p>`;
      updateTagCounts([]);
      return;
    }

    // Group: year -> city
    const byYear = new Map();
    for (const p of filtered) {
      if (!byYear.has(p.year)) byYear.set(p.year, new Map());
      const byCity = byYear.get(p.year);
      if (!byCity.has(p.city)) byCity.set(p.city, []);
      byCity.get(p.city).push(p);
    }

    const years = Array.from(byYear.keys()).sort((a, b) => String(b).localeCompare(String(a)));
    for (const y of years) {
      const yearSection = document.createElement("section");
      yearSection.classList.add("year-section");

      const yearTitle = document.createElement("h1");
      yearTitle.textContent = y;
      yearSection.appendChild(yearTitle);

      const byCity = byYear.get(y);
      const cities = Array.from(byCity.keys()).sort((a, b) => String(a).localeCompare(String(b)));

      for (const c of cities) {
        const eventSection = document.createElement("section");
        eventSection.classList.add("event-section");

        const eventTitle = document.createElement("h2");
        eventTitle.textContent = c;
        eventSection.appendChild(eventTitle);

        const imageContainer = document.createElement("div");
        imageContainer.classList.add("image-grid");

        const imgs = byCity.get(c).slice(); // keep JSON order
        
        for (const p of imgs) {
          const imgElement = document.createElement("img");
          imgElement.src = p.thumbUrl;
          imgElement.alt = "Gallery Image";
          imgElement.classList.add("photo-thumb");
          imgElement.setAttribute("loading", "lazy");

          const idx = currentLightboxList.indexOf(p.fullUrl);
          imgElement.addEventListener("click", () => openLightbox(idx));

          imageContainer.appendChild(imgElement);
        }

        eventSection.appendChild(imageContainer);
        yearSection.appendChild(eventSection);
      }

      gallery.appendChild(yearSection);
    }

    updateTagCounts(filtered);
  }

  function updateTagCounts(currentFiltered) {
    const tagCounts = new Map();
    for (const p of currentFiltered) {
      for (const t of p.semanticTags) {
        tagCounts.set(t, (tagCounts.get(t) || 0) + 1);
      }
    }

    const tagList = document.getElementById("tagList");
    if (!tagList) return;

    tagList.querySelectorAll(".tag-item").forEach(row => {
      const tag = row.dataset.tag;
      const countEl = row.querySelector(".tag-count");
      const count = tagCounts.get(tag) || 0;
      if (countEl) countEl.textContent = count ? `(${count})` : "";
      row.style.opacity = count ? "1" : "0.55";
    });

    // also update mobile tag panel counts (optional)
    const mTagsPanel = document.getElementById("mTagsPanel");
    if (mTagsPanel) {
      mTagsPanel.querySelectorAll(".mTagRow").forEach(row => {
        const tag = row.dataset.tag;
        const n = tagCounts.get(tag) || 0;
        row.style.opacity = n ? "1" : "0.55";
      });
    }
  }

  // --------------------------
  // Lightbox (keeps your existing behaviour + throbber)
  // --------------------------
  if (!document.getElementById("lightbox")) {
    document.body.insertAdjacentHTML("beforeend", `
      <div class="lightbox" id="lightbox">
        <span class="lightbox-close" id="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Expanded Image">
        <div class="lightbox-arrow left-arrow" id="left-arrow">&#10094;</div>
        <div class="lightbox-arrow right-arrow" id="right-arrow">&#10095;</div>
      </div>

      <div class="loading-throbber" id="loading-throbber" style="display:none;">
        <div class="spinner"></div>
        <p>Loading image...</p>
      </div>
    `);
  }

  function openLightbox(index) {
    if (!currentLightboxList.length) return;
    currentIndex = Math.max(0, Math.min(index, currentLightboxList.length - 1));
    const fullImageSrc = currentLightboxList[currentIndex];

    const th = document.getElementById("loading-throbber");
    if (th) th.style.display = "block";

    const lightboxImg = document.getElementById("lightbox-img");
    lightboxImg.src = "";
    lightboxImg.onload = () => {
      const t = document.getElementById("loading-throbber");
      if (t) t.style.display = "none";
    };

    lightboxImg.src = fullImageSrc;
    document.getElementById("lightbox").classList.add("active");
  }

  function closeLightbox() {
    document.getElementById("lightbox").classList.remove("active");
    const t = document.getElementById("loading-throbber");
    if (t) t.style.display = "none";
  }

  function prevImage() {
    if (!currentLightboxList.length) return;
    currentIndex = (currentIndex - 1 + currentLightboxList.length) % currentLightboxList.length;
    openLightbox(currentIndex);
  }

  function nextImage() {
    if (!currentLightboxList.length) return;
    currentIndex = (currentIndex + 1) % currentLightboxList.length;
    openLightbox(currentIndex);
  }

  document.getElementById("left-arrow").addEventListener("click", prevImage);
  document.getElementById("right-arrow").addEventListener("click", nextImage);
  document.getElementById("lightbox-close").addEventListener("click", closeLightbox);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeLightbox();
    if (event.key === "ArrowLeft") prevImage();
    if (event.key === "ArrowRight") nextImage();
  });

  let touchStartX = 0;
  let touchEndX = 0;

  document.getElementById("lightbox").addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0].screenX;
  });

  document.getElementById("lightbox").addEventListener("touchend", (event) => {
    touchEndX = event.changedTouches[0].screenX;
    if (touchStartX - touchEndX > 50) nextImage();
    if (touchEndX - touchStartX > 50) prevImage();
  });

  // --------------------------
  // Init
  // --------------------------
  buildFilters();
  render();
});

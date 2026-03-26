// Theme picker: create UI, apply themes by setting CSS variables, persist in localStorage
document.addEventListener("DOMContentLoaded", function () {
  const THEMES = [
    {
      id: "default",
      name: "Default",
      vars: {}
    },
    {
      id: "sunset",
      name: "Sunset",
      vars: {
        "--primary-color": "#ff6b81",
        "--primary-dark": "#e64a6f",
        "--secondary-color": "#ffc371",
        "--bg-color": "#fff7f8",
        "--card-color": "#fff4f6",
        "--text-color": "#2a2a2a",
        "--border-color": "#ffe6ea"
      }
    },
    {
      id: "midnight",
      name: "Midnight",
      vars: {
        "--primary-color": "#8a7fff",
        "--primary-dark": "#6c63ff",
        "--secondary-color": "#4ecdc4",
        "--bg-color": "#0f1724",
        "--card-color": "#111827",
        "--text-color": "#e6eef8",
        "--text-light": "#b7c3db",
        "--border-color": "#1f2937"
      }
    },
    {
      id: "forest",
      name: "Forest",
      vars: {
        "--primary-color": "#2fa66b",
        "--primary-dark": "#22804f",
        "--secondary-color": "#ffc857",
        "--bg-color": "#f3fff6",
        "--card-color": "#f7fff9",
        "--text-color": "#0b2e1a",
        "--border-color": "#e6f4ea"
      }
    },
    {
      id: "rose",
      name: "Rose",
      vars: {
        "--primary-color": "#ff8aa0",
        "--primary-dark": "#ff5f84",
        "--secondary-color": "#ffd1e0",
        "--bg-color": "#fff6f8",
        "--card-color": "#fff1f4",
        "--text-color": "#2b0a12",
        "--border-color": "#ffe7ee"
      }
    }
  ];

  const storageKey = "sms_theme_choice";

  // Create picker container
  const picker = document.createElement("div");
  picker.className = "theme-picker";
  picker.innerHTML = `
    <button class="palette-button" aria-label="Theme palette">🎨</button>
    <div class="palette-panel hidden" aria-hidden="true"></div>
  `;
  document.body.appendChild(picker);

  const panel = picker.querySelector(".palette-panel");
  const button = picker.querySelector(".palette-button");

  // populate panel
  THEMES.forEach((t) => {
    const sw = document.createElement("button");
    sw.className = "color-swatch";
    sw.type = "button";
    sw.title = t.name;
    sw.dataset.themeId = t.id;
    // show swatch preview using primary color or fallback
    const preview = document.createElement("span");
    preview.className = "swatch-preview";
    preview.style.background =
      t.vars["--primary-color"] || getComputedStyle(document.documentElement).getPropertyValue("--primary-color") || "#6c63ff";
    const label = document.createElement("span");
    label.className = "swatch-label";
    label.textContent = t.name;
    sw.appendChild(preview);
    sw.appendChild(label);
    panel.appendChild(sw);

    sw.addEventListener("click", () => {
      applyTheme(t);
      saveTheme(t.id);
      closePanel();
    });
  });

  // Reset option
  const resetBtn = document.createElement("button");
  resetBtn.className = "color-swatch reset";
  resetBtn.type = "button";
  resetBtn.title = "Reset to default";
  resetBtn.innerHTML = '<span class="swatch-preview reset-preview">⟲</span><span class="swatch-label">Reset</span>';
  panel.appendChild(resetBtn);
  resetBtn.addEventListener("click", () => {
    clearTheme();
    closePanel();
  });

  function openPanel() {
    panel.classList.remove("hidden");
    panel.setAttribute("aria-hidden", "false");
    button.classList.add("active");
  }
  function closePanel() {
    panel.classList.add("hidden");
    panel.setAttribute("aria-hidden", "true");
    button.classList.remove("active");
  }
  button.addEventListener("click", (e) => {
    e.stopPropagation();
    if (panel.classList.contains("hidden")) openPanel(); else closePanel();
  });

  // close when clicking outside
  document.addEventListener("click", (e) => {
    if (!picker.contains(e.target)) closePanel();
  });

  // apply theme by writing CSS variables
  function applyTheme(theme) {
    const vars = theme.vars || {};
    const root = document.documentElement;
    // apply provided vars, leave others intact for default
    Object.keys(vars).forEach((k) => {
      root.style.setProperty(k, vars[k]);
    });
    // small visual feedback
    document.body.classList.add("theme-applied");
    setTimeout(() => document.body.classList.remove("theme-applied"), 800);
  }

  function clearTheme() {
    // remove theme overrides (clear inline style for variables defined in themes)
    const root = document.documentElement;
    THEMES.forEach((t) => {
      Object.keys(t.vars || {}).forEach((k) => {
        root.style.removeProperty(k);
      });
    });
    localStorage.removeItem(storageKey);
  }

  function saveTheme(id) {
    try {
      localStorage.setItem(storageKey, id);
    } catch (e) {
      // ignore storage errors
    }
  }

  function restoreTheme() {
    try {
      const id = localStorage.getItem(storageKey);
      if (!id) return;
      const theme = THEMES.find((t) => t.id === id);
      if (theme) applyTheme(theme);
    } catch (e) {}
  }

  // initialize
  restoreTheme();
});
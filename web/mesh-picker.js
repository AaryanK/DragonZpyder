// Accessible, compact visual pickers; native <select> remains the source of truth
// for the existing AI Mesh model/task controllers and their security checks.
let activePicker = null;

function modernPicker(select, { searchable = false, kind = "task" } = {}) {
  if (!select || select.dataset.modernized === "true") return;
  select.dataset.modernized = "true";
  const root = document.createElement("div");
  root.className = "mesh-picker mesh-picker--" + kind;
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "mesh-picker-trigger";
  trigger.setAttribute("aria-label", select.getAttribute("aria-label") || "Choose option");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  const value = document.createElement("span");
  value.className = "mesh-picker-value";
  const chevron = document.createElement("span");
  chevron.className = "mesh-picker-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "⌄";
  trigger.append(value, chevron);

  const popover = document.createElement("div");
  popover.className = "mesh-picker-popover";
  popover.hidden = true;
  const id = select.id + "-modern-list";
  const options = document.createElement("div");
  options.className = "mesh-picker-options";
  options.id = id;
  options.setAttribute("role", "listbox");
  options.setAttribute("aria-label", select.getAttribute("aria-label") || "Options");
  trigger.setAttribute("aria-controls", id);
  let search;
  if (searchable) {
    const searchBox = document.createElement("div");
    searchBox.className = "mesh-picker-search-wrap";
    search = document.createElement("input");
    search.type = "search";
    search.className = "mesh-picker-search";
    search.placeholder = "Search models…";
    search.setAttribute("aria-label", "Search available models");
    search.autocomplete = "off";
    searchBox.append(search);
    popover.append(searchBox);
  }
  popover.append(options);
  root.append(trigger, popover);
  select.after(root);
  select.classList.add("mesh-native-select");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  const close = ({ focus = false } = {}) => {
    popover.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    root.classList.remove("open");
    if (activePicker === close) activePicker = null;
    if (focus) trigger.focus();
  };

  const draw = () => {
    const selected = select.selectedOptions[0];
    value.textContent = selected?.textContent?.trim() || "Select model";
    trigger.title = selected?.textContent?.trim() || "Select model";
    const query = (search?.value || "").trim().toLocaleLowerCase();
    options.replaceChildren();
    let count = 0;
    for (const option of select.options) {
      const label = option.textContent.trim();
      if (query && !label.toLocaleLowerCase().includes(query) &&
          !option.value.toLocaleLowerCase().includes(query)) continue;
      const item = document.createElement("button");
      item.className = "mesh-picker-option";
      item.type = "button";
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.value === select.value));
      item.disabled = option.disabled;
      const text = document.createElement("span");
      text.className = "mesh-picker-option-text";
      text.textContent = label;
      const check = document.createElement("span");
      check.className = "mesh-picker-check";
      check.setAttribute("aria-hidden", "true");
      check.textContent = option.value === select.value ? "✓" : "";
      item.append(text, check);
      item.addEventListener("click", () => {
        if (item.disabled) return;
        select.value = option.value;
        // Existing mesh.js change handlers remain authoritative.
        select.dispatchEvent(new Event("change", { bubbles: true }));
        draw();
        close({ focus: true });
      });
      options.append(item);
      count++;
    }
    if (!count) {
      const none = document.createElement("p");
      none.className = "mesh-picker-empty";
      none.textContent = "No matching models";
      options.append(none);
    }
  };

  const open = () => {
    if (activePicker && activePicker !== close) activePicker();
    activePicker = close;
    draw();
    popover.hidden = false;
    root.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
    if (search) {
      search.value = "";
      draw();
      search.focus();
    } else {
      options.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    }
  };
  trigger.addEventListener("click", () => popover.hidden ? open() : close());
  search?.addEventListener("input", draw);
  popover.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); close({ focus: true }); return; }
    const buttons = Array.from(options.querySelectorAll(".mesh-picker-option:not(:disabled)"));
    if (event.key === "Enter" && event.target === search && buttons.length) {
      event.preventDefault(); buttons[0].click(); return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const current = buttons.indexOf(document.activeElement);
    const step = event.key === "ArrowDown" ? 1 : -1;
    buttons[(current + step + buttons.length) % buttons.length]?.focus();
  });
  document.addEventListener("pointerdown", event => {
    if (!popover.hidden && !root.contains(event.target)) close();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !popover.hidden) close({ focus: true });
  });
  const observer = new MutationObserver(draw);
  observer.observe(select, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["disabled"] });
  select.addEventListener("change", draw);
  draw();
}

modernPicker(document.getElementById("mesh-task"), { kind: "task" });
modernPicker(document.getElementById("mesh-model"), { kind: "model", searchable: true });

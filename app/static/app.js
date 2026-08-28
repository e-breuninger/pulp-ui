(function () {
  // Hides items whose text doesn't match `input` (and, if given, whose
  // `data-type` doesn't match `typeFilter`). `haystack` says where an item's
  // searchable text comes from - the only thing cards and table rows differ in.
  function initFilter({ input, items, noResults, haystack, typeFilter }) {
    if (!input || !items.length) return;

    function apply() {
      const query = input.value.trim().toLowerCase();
      const type = typeFilter ? typeFilter.value : "";
      let visible = 0;
      for (const item of items) {
        const matches =
          (!query || haystack(item).includes(query)) &&
          (!type || item.dataset.type === type);
        item.hidden = !matches;
        if (matches) visible += 1;
      }
      if (noResults) noResults.hidden = visible !== 0;
    }

    input.addEventListener("input", apply);
    if (typeFilter) typeFilter.addEventListener("change", apply);
  }

  function initDistributionSearch() {
    const table = document.getElementById("distribution-table");
    if (!table) return;
    initFilter({
      input: document.getElementById("distribution-search"),
      typeFilter: document.getElementById("distribution-type-filter"),
      items: Array.from(table.querySelectorAll("tbody tr")),
      noResults: document.getElementById("distribution-no-results"),
      // Prebuilt on the row, so base paths and URLs stay searchable now that the
      // table doesn't show them.
      haystack: (row) => row.dataset.search || "",
    });
  }

  function initTableSearch() {
    const table = document.getElementById("content-table");
    if (!table) return;
    initFilter({
      input: document.getElementById("content-search"),
      items: Array.from(table.querySelectorAll("tbody tr")),
      noResults: document.getElementById("content-no-results"),
      haystack: (row) => row.textContent.toLowerCase(),
    });
  }

  function initSortableTables() {
    // `numeric` so version strings like 1.2.10 sort after 1.2.9.
    const collator = new Intl.Collator(undefined, {
      numeric: true,
      sensitivity: "base",
    });

    // A cell's sort key: `data-sort` when the markup provides one, else its text.
    // Displayed numbers are grouped ("5,977"), and the collator splits on the
    // separator - it compares 5 against 169 and puts 5,977 first - so numeric
    // columns hand over the raw value instead.
    const key = (row, column) => {
      const cell = row.cells[column];
      if (!cell) return "";
      const sortValue = cell.dataset.sort;
      return sortValue === undefined ? cell.textContent.trim() : sortValue;
    };

    function compare(a, b) {
      const numberA = Number(a);
      const numberB = Number(b);
      if (a !== "" && b !== "" && !isNaN(numberA) && !isNaN(numberB)) {
        return numberA - numberB;
      }
      return collator.compare(a, b);
    }

    for (const table of document.querySelectorAll("table")) {
      const body = table.tBodies[0];
      const headers = Array.from(table.querySelectorAll("thead th"));
      if (!body || !headers.length) continue;

      headers.forEach((header, column) => {
        header.tabIndex = 0;
        header.setAttribute("role", "button");
        header.classList.add("sortable");

        function sort() {
          const ascending = header.getAttribute("aria-sort") !== "ascending";
          for (const other of headers) other.removeAttribute("aria-sort");
          header.setAttribute("aria-sort", ascending ? "ascending" : "descending");

          const rows = Array.from(body.rows).sort(
            (a, b) =>
              compare(key(a, column), key(b, column)) * (ascending ? 1 : -1),
          );
          body.append(...rows);
        }

        header.addEventListener("click", sort);
        header.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          sort();
        });
      });
    }
  }

  function initThemeToggle() {
    const button = document.getElementById("theme-toggle");
    if (!button) return;

    button.addEventListener("click", () => {
      const next =
        document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("theme", next);
    });
  }

  function initCopyButtons() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-copy]");
      if (!button) return;
      navigator.clipboard.writeText(button.dataset.copy).then(() => {
        const original = button.textContent;
        button.textContent = "Copied!";
        setTimeout(() => (button.textContent = original), 1200);
      });
    });
  }

  function init() {
    initDistributionSearch();
    initTableSearch();
    initSortableTables();
    initThemeToggle();
    initCopyButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

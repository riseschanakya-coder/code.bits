const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector(".nav-links");
const themeSelect = document.querySelector("#theme-select");
const pageLoader = document.querySelector(".page-loader");
const installButton = document.querySelector("#install-app");
let installPrompt;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  if (installButton) installButton.hidden = false;
});

window.addEventListener("appinstalled", () => {
  installPrompt = null;
  if (installButton) installButton.hidden = true;
});

if (installButton) {
  installButton.addEventListener("click", async () => {
    if (!installPrompt) return;

    await installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    installButton.hidden = true;
  });
}

if (pageLoader) {
  document.querySelectorAll('a[href]').forEach((link) => {
    link.addEventListener("click", (event) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        link.target ||
        link.hasAttribute("download")
      ) {
        return;
      }

      const destination = new URL(link.href, window.location.href);
      if (
        destination.origin === window.location.origin &&
        (destination.pathname !== window.location.pathname || destination.search !== window.location.search)
      ) {
        pageLoader.classList.add("is-loading");
      }
    });
  });

  window.addEventListener("pageshow", () => {
    pageLoader.classList.remove("is-loading");
  });
}

if (navToggle && navLinks) {
  navToggle.addEventListener("click", () => {
    navLinks.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(navLinks.classList.contains("open")));
  });
}

if (themeSelect) {
  const currentTheme = localStorage.getItem("codedaily-theme") || "light";
  themeSelect.value = currentTheme;
  document.documentElement.dataset.theme = currentTheme;

  themeSelect.addEventListener("change", () => {
    localStorage.setItem("codedaily-theme", themeSelect.value);
    document.documentElement.dataset.theme = themeSelect.value;
  });
}

const searchInput = document.querySelector("#problem-search");
const filterButtons = document.querySelectorAll(".filter-tabs button");
const problemRows = document.querySelectorAll(".problem-row");
const problemEmpty = document.querySelector("#problem-empty");
let activeFilter = "all";

function filterProblems() {
  const query = (searchInput?.value || "").trim().toLowerCase();
  let visibleCount = 0;

  problemRows.forEach((row) => {
    const searchText = row.dataset.search || row.textContent.toLowerCase();
    const matchesSearch = searchText.includes(query);
    const matchesDifficulty = activeFilter === "all" || row.dataset.difficulty === activeFilter;
    const isVisible = matchesSearch && matchesDifficulty;

    row.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });

  if (problemEmpty) {
    problemEmpty.hidden = visibleCount > 0;
  }
}

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    filterButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeFilter = button.dataset.filter;
    filterProblems();
  });
});

if (searchInput) {
  searchInput.addEventListener("input", filterProblems);
}

filterProblems();

const revealTargets = document.querySelectorAll(
  ".page-shell > .dashboard-hero, .page-shell > .page-header, .page-shell > .daily-summary, " +
  ".page-shell > .coding-layout > *, .page-shell > .profile-grid > *, " +
  ".page-shell > .stats-grid > *, .page-shell > .quick-actions > *, " +
  ".page-shell > .difficulty-breakdown > *, .page-shell > .activity-panel, " +
  ".page-shell .activity-row, .page-shell .problem-list > .problem-row, " +
  ".page-shell > .empty-state, .auth-card"
);
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if ("IntersectionObserver" in window && !prefersReducedMotion) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: "0px 0px -32px 0px"
  });

  revealTargets.forEach((target) => {
    target.classList.add("scroll-reveal");
    revealObserver.observe(target);
  });
}

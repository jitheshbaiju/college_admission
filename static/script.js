const courseFilters = document.querySelectorAll("[data-course-filter]");
const courseCards = document.querySelectorAll("[data-course-card]");
const courseResultsCount = document.querySelector(".course-results-count strong");
const courseFilterEmpty = document.querySelector("[data-filter-empty]");

if (courseFilters.length && courseCards.length) {
    courseFilters.forEach((filter) => {
        filter.addEventListener("click", () => {
            const selectedCategory = filter.dataset.courseFilter;
            let visibleCount = 0;

            courseFilters.forEach((button) => {
                const isSelected = button === filter;
                button.classList.toggle("is-active", isSelected);
                button.setAttribute("aria-pressed", String(isSelected));
            });

            courseCards.forEach((card) => {
                const matches = selectedCategory === "all" || card.dataset.category === selectedCategory;
                card.hidden = !matches;
                if (matches) visibleCount += 1;
            });

            if (courseResultsCount) {
                courseResultsCount.textContent = String(visibleCount);
            }
            if (courseFilterEmpty) {
                courseFilterEmpty.hidden = visibleCount > 0;
            }
        });
    });
}
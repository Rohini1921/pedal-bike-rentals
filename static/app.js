const bikeGrid = document.querySelector("#bike-grid");
const bikeSelect = document.querySelector("#bike-select");
const bookingForm = document.querySelector("#booking-form");
const formMessage = document.querySelector("#form-message");
const accountLinks = document.querySelector("#account-links");
const authDialog = document.querySelector("#auth-dialog");
const startTimeInput = bookingForm.querySelector('[name="start_time"]');
const endTimeInput = bookingForm.querySelector('[name="end_time"]');

function localDateTimeValue(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function updateBookingTimeLimits() {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 1, 0, 0);
  const minimum = localDateTimeValue(now);
  startTimeInput.min = minimum;
  endTimeInput.min = startTimeInput.value || minimum;
}

updateBookingTimeLimits();
startTimeInput.addEventListener("change", () => {
  endTimeInput.min = startTimeInput.value || localDateTimeValue(new Date());
});

function showAuthPanel(mode) {
  for (const panel of authDialog.querySelectorAll("[data-auth-panel]")) {
    panel.hidden = panel.dataset.authPanel !== mode;
  }
  const activePanel = authDialog.querySelector(`[data-auth-panel="${mode}"]`);
  activePanel.querySelector("input").focus();
}

accountLinks.addEventListener("click", (event) => {
  const button = event.target.closest("[data-open-auth]");
  if (!button) return;
  showAuthPanel(button.dataset.openAuth);
  authDialog.showModal();
});

authDialog.querySelector(".auth-close").addEventListener("click", () => authDialog.close());
authDialog.addEventListener("click", (event) => {
  if (event.target === authDialog) authDialog.close();
});

authDialog.querySelectorAll("[data-switch-auth]").forEach((button) => {
  button.addEventListener("click", () => showAuthPanel(button.dataset.switchAuth));
});

authDialog.querySelectorAll(".modal-auth-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = form.querySelector(".auth-message");
    message.textContent = "";
    message.className = "auth-message";
    const values = Object.fromEntries(new FormData(form));
    const isAdmin = values.account_type === "admin";
    const endpoint = isAdmin
      ? (form.dataset.mode === "signup" ? "/api/admin-signup" : "/api/admin-login")
      : `/api/${form.dataset.mode}`;
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Please try again.");
      window.location.assign(isAdmin ? "/admin/dashboard" : "/");
    } catch (error) {
      message.textContent = error.message;
      message.classList.add("error-message");
    }
  });
});

async function loadAccountLinks() {
  try {
    const response = await fetch("/api/session");
    if (!response.ok) throw new Error("Could not check account status.");
    const result = await response.json();
    if (result.authenticated) {
      accountLinks.innerHTML = `<span class="account-greeting">Hi, ${escapeHtml(result.user.full_name)}</span><button class="account-logout" type="button">Log out</button>`;
      accountLinks.querySelector(".account-logout").addEventListener("click", async () => {
        const logoutResponse = await fetch("/api/logout", { method: "POST" });
        if (!logoutResponse.ok) throw new Error("Could not log out. Please try again.");
        window.location.reload();
      });
    }
  } catch (error) {
    console.error(error);
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

async function loadBikes() {
  try {
    const response = await fetch("/api/bikes");
    const bikes = await response.json();
    if (!response.ok) throw new Error(bikes.error || "Could not load bikes.");
    if (bikes.length === 0) {
      bikeGrid.innerHTML = '<p class="loading-state">No bikes are available right now. Please check back soon.</p>';
      return;
    }
    bikeGrid.innerHTML = bikes.map((bike, index) => `
      <article class="bike-card">
        <div class="bike-image">
          <img src="${escapeHtml(bike.image_url)}" alt="${escapeHtml(bike.name)}" loading="lazy">
          <span class="bike-number">0${index + 1}</span>
          <span class="bike-badge">${escapeHtml(bike.category)}</span>
        </div>
        <div class="bike-info">
          <div><h3>${escapeHtml(bike.name)}</h3><p>${escapeHtml(bike.description)}</p></div>
          <div class="bike-price"><strong>$${Number(bike.hourly_rate).toFixed(2)}</strong><span>/ hour</span></div>
        </div>
        <a class="bike-link" href="#booking" data-bike-id="${bike.bike_id}">Book this bike <span aria-hidden="true">↗</span></a>
      </article>
    `).join("");
    bikeSelect.innerHTML = '<option value="">Select a bike</option>' + bikes.map((bike) =>
      `<option value="${bike.bike_id}">${escapeHtml(bike.name)} — $${Number(bike.hourly_rate).toFixed(2)}/hr</option>`
    ).join("");
  } catch (error) {
    bikeGrid.innerHTML = `<p class="loading-state error-state">${escapeHtml(error.message)} Make sure MySQL is running and DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME are set.</p>`;
  }
}

bikeGrid.addEventListener("click", (event) => {
  const link = event.target.closest("[data-bike-id]");
  if (link) bikeSelect.value = link.dataset.bikeId;
});

bookingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";
  formMessage.className = "form-message";
  updateBookingTimeLimits();
  const values = Object.fromEntries(new FormData(bookingForm));
  if (values.start_time < startTimeInput.min || values.end_time <= values.start_time) {
    formMessage.textContent = "Choose a future start time and an end time after it.";
    formMessage.classList.add("error-message");
    return;
  }
  try {
    const response = await fetch("/api/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not complete your booking.");
    formMessage.textContent = `${result.message} Reference #${result.rental_id}.`;
    formMessage.classList.add("success-message");
    bookingForm.reset();
  } catch (error) {
    formMessage.textContent = error.message;
    formMessage.classList.add("error-message");
  }
});

const menuToggle = document.querySelector(".menu-toggle");
menuToggle.addEventListener("click", () => {
  const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isOpen));
  document.querySelector(".main-nav").classList.toggle("nav-open", !isOpen);
});

loadBikes();
loadAccountLinks();

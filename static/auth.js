const authForm = document.querySelector("#auth-form");
const authMessage = document.querySelector("#auth-message");

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authMessage.textContent = "";
  authMessage.className = "auth-message";
  const mode = authForm.dataset.mode;
  const values = Object.fromEntries(new FormData(authForm));
  const isAdmin = values.account_type === "admin";
  const endpoint = isAdmin
    ? (mode === "signup" ? "/api/admin-signup" : "/api/admin-login")
    : `/api/${mode}`;
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
    authMessage.textContent = error.message;
    authMessage.classList.add("error-message");
  }
});

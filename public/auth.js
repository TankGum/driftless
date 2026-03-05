// Auto-login: read auth_token from URL query param and set as cookie
(function () {
  var TAB_TITLE = "Driftless Chatbot";
  var FAVICON_PATH = "/public/favicon.svg";

  function ensureTitleAndIcon() {
    if (document.title !== TAB_TITLE) {
      document.title = TAB_TITLE;
    }

    var icon = document.querySelector("link[rel~='icon']");
    if (!icon) {
      icon = document.createElement("link");
      icon.setAttribute("rel", "icon");
      document.head.appendChild(icon);
    }
    if (icon.getAttribute("href") !== FAVICON_PATH) {
      icon.setAttribute("type", "image/svg+xml");
      icon.setAttribute("href", FAVICON_PATH);
    }
  }

  ensureTitleAndIcon();
  window.addEventListener("load", ensureTitleAndIcon);
  setTimeout(ensureTitleAndIcon, 300);
  setTimeout(ensureTitleAndIcon, 1200);

  var params = new URLSearchParams(window.location.search);
  var token = params.get("auth_token");
  if (token) {
    document.cookie = "auth_token=" + token + "; path=/; max-age=86400; SameSite=Lax";
    // Remove token from URL to keep it clean
    params.delete("auth_token");
    var newUrl = window.location.pathname;
    var remaining = params.toString();
    if (remaining) newUrl += "?" + remaining;
    window.history.replaceState({}, "", newUrl);
  }
})();

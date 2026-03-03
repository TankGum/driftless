// Auto-login: read auth_token from URL query param and set as cookie
(function () {
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

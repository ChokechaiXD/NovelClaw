/* Shared lazy loader for admin page modules. */

(function () {
  const promises = {};

  function loadOnce(key, src, errorMessage) {
    if (!promises[key]) {
      promises[key] = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.async = false;
        script.onload = resolve;
        script.onerror = () => reject(new Error(errorMessage || `Failed to load ${src}`));
        document.head.appendChild(script);
      });
    }
    return promises[key];
  }

  window.AdminPageLoader = { loadOnce };
})();

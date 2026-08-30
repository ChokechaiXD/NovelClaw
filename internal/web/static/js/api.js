export function createAPIClient({ onError } = {}) {
  return async function api(path, options = {}) {
    const { silent = false, headers = {}, ...fetchOptions } = options;
    try {
      const res = await fetch(path, {
        cache: 'no-store',
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(payload.error || `HTTP ${res.status}`);
      }
      if (res.status === 204) return null;
      return await res.json();
    } catch (err) {
      if (!silent && typeof onError === 'function') onError(err);
      throw err;
    }
  };
}

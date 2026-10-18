export function redirectSystemPath({ path }: { path: string; initial: boolean }) {
  try {
    const url = new URL(path, 'nascon://app');
    if (url.protocol === 'nascon:' && url.hostname === 'entity') return `/entity/${encodeURIComponent(url.pathname.replace(/^\//, ''))}`;
    if (url.protocol === 'nascon:' && url.hostname === 'stream') return `/stream/${encodeURIComponent(url.pathname.replace(/^\//, ''))}`;
    return path;
  } catch {
    return '/scanner?error=invalid-link';
  }
}


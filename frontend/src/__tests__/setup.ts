/**
 * Vitest 全局 setup：为 node 环境补齐浏览器 API。
 *
 * 仅在测试中使用，不影响生产代码。
 */
export {};

// localStorage polyfill（最小实现，仅供测试）
const _store = new Map<string, string>();

if (typeof globalThis.localStorage === "undefined") {
  const localStoragePolyfill = {
    getItem(key: string): string | null {
      return _store.has(key) ? _store.get(key)! : null;
    },
    setItem(key: string, value: string): void {
      _store.set(key, String(value));
    },
    removeItem(key: string): void {
      _store.delete(key);
    },
    clear(): void {
      _store.clear();
    },
    key(index: number): string | null {
      return Array.from(_store.keys())[index] ?? null;
    },
    get length(): number {
      return _store.size;
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: localStoragePolyfill,
    configurable: true,
    writable: true,
  });
}

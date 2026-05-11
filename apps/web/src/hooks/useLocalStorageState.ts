import { useState } from "react";

export function useLocalStorageState(key: string, fallback = "") {
  const [value, setValue] = useState(() => {
    try {
      return window.localStorage.getItem(key) ?? fallback;
    } catch {
      return fallback;
    }
  });

  function setStoredValue(nextValue: string) {
    setValue(nextValue);
    try {
      window.localStorage.setItem(key, nextValue);
    } catch {
      // Storage may be unavailable in restricted browser contexts.
    }
  }

  return [value, setStoredValue] as const;
}

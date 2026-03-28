import { useEffect, useState } from "react";

/**
 * Debounce a value by the given delay in milliseconds.
 * Returns the debounced value that only updates after the delay has passed
 * since the last change to the input value.
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}

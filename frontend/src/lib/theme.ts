import { useEffect, useState } from "react";

// "system" follows the computer's setting; "light" and "dark" are remembered
// in this browser only (localStorage). The theme is <html data-theme="...">.
export type ThemeChoice = "system" | "light" | "dark";

const KEY = "dap-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function stored(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function apply(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "system" && matchMedia(DARK_QUERY).matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function useTheme(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const [choice, setChoice] = useState<ThemeChoice>(stored);

  useEffect(() => {
    apply(choice);
    try {
      if (choice === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      // private window: the choice lasts until the page closes
    }
    if (choice !== "system") return;
    const media = matchMedia(DARK_QUERY);
    const follow = () => apply("system");
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, [choice]);

  return [choice, setChoice];
}

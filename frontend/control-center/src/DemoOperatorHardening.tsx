import { useEffect } from "react";
import "./demo-operator-hardening.css";

function activeDataLayersButton(): HTMLButtonElement | null {
  if (!document.body.classList.contains("data-layers-active")) return null;
  return document.querySelector<HTMLButtonElement>(".ow-data-layers-nav button");
}

function closeDataLayers(): void {
  activeDataLayersButton()?.click();
}

export default function DemoOperatorHardening() {
  useEffect(() => {
    const onNavigationClick = (event: MouseEvent) => {
      const target = event.target as Element | null;
      const navigationButton = target?.closest<HTMLButtonElement>(".ow-sidebar nav button");
      if (!navigationButton || navigationButton.closest(".ow-data-layers-nav")) return;

      // Data Layers is a portal overlay on the canonical workspace. Close it first so
      // a regular primary-navigation click can never leave a hidden sticky overlay.
      closeDataLayers();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      closeDataLayers();
    };

    document.addEventListener("click", onNavigationClick, true);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onNavigationClick, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return null;
}

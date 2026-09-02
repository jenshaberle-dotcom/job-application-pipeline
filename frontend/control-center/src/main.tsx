import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import DemoApplicationWorkspace from "./DemoApplicationWorkspace";
import EvidencePreviewPanel from "./EvidencePreviewPanel";
import RuntimeErrorBoundary from "./RuntimeErrorBoundary";
import { installProductPayloadRuntimeAdapter } from "./productPayloadRuntimeAdapter";
import "./styles.css";
import "./compact-control-center.css";

installProductPayloadRuntimeAdapter();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <RuntimeErrorBoundary>
      <App />
      <EvidencePreviewPanel />
      <DemoApplicationWorkspace />
    </RuntimeErrorBoundary>
  </StrictMode>
);

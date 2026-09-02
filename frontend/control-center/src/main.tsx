import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ApplicationWorkspaceEventBridge from "./ApplicationWorkspaceEventBridge";
import DemoApplicationWorkspace from "./DemoApplicationWorkspace";
import EvidencePreviewPanel from "./EvidencePreviewPanel";
import OperatorWorkspace from "./OperatorWorkspace";
import RuntimeErrorBoundary from "./RuntimeErrorBoundary";
import { installProductPayloadRuntimeAdapter } from "./productPayloadRuntimeAdapter";
import "./styles.css";
import "./compact-control-center.css";
import "./demo-operator-focus.css";

installProductPayloadRuntimeAdapter();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <RuntimeErrorBoundary>
      <OperatorWorkspace />
      <EvidencePreviewPanel />
      <DemoApplicationWorkspace />
      <ApplicationWorkspaceEventBridge />
    </RuntimeErrorBoundary>
  </StrictMode>
);

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ApplicationWorkspaceEventBridge from "./ApplicationWorkspaceEventBridge";
import DataLayersTab from "./DataLayersTab";
import DemoApplicationWorkspace from "./DemoApplicationWorkspace";
import DemoOperatorHardening from "./DemoOperatorHardening";
import DemoProductPolish from "./DemoProductPolish";
import DemoTruthRibbon from "./DemoTruthRibbon";
import EvidencePreviewPanel from "./EvidencePreviewPanel";
import App from "./OperatorWorkspace";
import RuntimeErrorBoundary from "./RuntimeErrorBoundary";
import { installProductPayloadRuntimeAdapter } from "./productPayloadRuntimeAdapter";
import "./styles.css";
import "./compact-control-center.css";
import "./demo-operator-focus.css";
import "./product-finish-ux.css";

installProductPayloadRuntimeAdapter();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <RuntimeErrorBoundary>
      <App />
      <DataLayersTab />
      <DemoOperatorHardening />
      <DemoProductPolish />
      <DemoTruthRibbon />
      <EvidencePreviewPanel />
      <DemoApplicationWorkspace />
      <ApplicationWorkspaceEventBridge />
    </RuntimeErrorBoundary>
  </StrictMode>
);

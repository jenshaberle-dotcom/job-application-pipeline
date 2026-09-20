import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AboutPanel from "./AboutPanel";
import ApplicationWorkspaceEventBridge from "./ApplicationWorkspaceEventBridge";
import DataLayersTab from "./DataLayersTab";
import DemoApplicationWorkspace from "./DemoApplicationWorkspace";
import DemoOperatorHardening from "./DemoOperatorHardening";
import DemoProductPolish from "./DemoProductPolish";
import DemoTruthRibbon from "./DemoTruthRibbon";
import F4cSourceHealthSurface from "./F4cSourceHealthSurface";
import App from "./OperatorWorkspace";
import RuntimeErrorBoundary from "./RuntimeErrorBoundary";
import { ProductTruthProvider } from "./ProductTruthContext";
import "./styles.css";
import "./compact-control-center.css";
import "./demo-operator-focus.css";
import "./product-finish-ux.css";


const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <RuntimeErrorBoundary>
      <ProductTruthProvider>
        <App />
        <DataLayersTab />
        <AboutPanel />
        <DemoOperatorHardening />
        <DemoProductPolish />
        <DemoTruthRibbon />
        <F4cSourceHealthSurface />
        <DemoApplicationWorkspace />
        <ApplicationWorkspaceEventBridge />
      </ProductTruthProvider>
    </RuntimeErrorBoundary>
  </StrictMode>
);

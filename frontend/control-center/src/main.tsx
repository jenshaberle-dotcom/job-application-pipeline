import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AboutPanel from "./AboutPanel";
import DataLayersTab from "./DataLayersTab";
import ApplicationWorkspace from "./ApplicationWorkspace";
import OperatorHardening from "./OperatorHardening";
import ProductPolish from "./ProductPolish";
import ProductTruthRibbon from "./ProductTruthRibbon";
import F4cSourceHealthSurface from "./F4cSourceHealthSurface";
import App from "./OperatorWorkspace";
import RuntimeErrorBoundary from "./RuntimeErrorBoundary";
import { ProductTruthProvider } from "./ProductTruthContext";
import "./styles.css";
import "./compact-control-center.css";
import "./operator-focus.css";
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
        <OperatorHardening />
        <ProductPolish />
        <ProductTruthRibbon />
        <F4cSourceHealthSurface />
        <ApplicationWorkspace />
      </ProductTruthProvider>
    </RuntimeErrorBoundary>
  </StrictMode>
);

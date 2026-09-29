import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./product-truth-ribbon.css";

export default function ProductTruthRibbon() {
  const [topline, setTopline] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setTopline(document.querySelector<HTMLElement>(".ow-topline"));
  }, []);

  if (!topline) return null;

  return createPortal(
    <div className="product-truth-ribbon" aria-label="Product truth and application authority boundaries">
      <span title="Control Center values come from the current Product V1 runtime and local persistence; no synthetic rows are fabricated."><i className="live" />Live DB truth</span>
      <span title="Application output is draft_for_review and remains subject to human review."><i className="review" />Review only</span>
      <span title="The product UI has no automatic application submission or send authority."><i className="blocked" />No submit / send</span>
    </div>,
    topline,
  );
}

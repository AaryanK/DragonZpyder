import React, { createContext, useContext } from "react";

export const RuntimeContext = createContext({ status: "checking", year: 2026 });
export function RuntimeDot() {
  const { status } = useContext(RuntimeContext);
  return (
    <span id="runtime-dot" className={status === "online" ? "online" : status === "error" ? "error" : ""}
      style={{ display: "inline-block", width: "7px", height: "7px", borderRadius: "50%", background: "#858a81" }}
      aria-hidden="true" />
  );
}
export function RuntimeText() {
  const { status } = useContext(RuntimeContext);
  return <span id="runtime-text" aria-live="polite">
    {status === "online" ? "Operly runtime reachable"
      : status === "error" ? "Runtime status unavailable" : "Checking runtime…"}
  </span>;
}
export function RuntimeYear() {
  const { year } = useContext(RuntimeContext);
  return <span id="year">{year}</span>;
}

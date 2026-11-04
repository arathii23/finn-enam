import type { ResearchMode } from "./api";

export function ResearchModePicker({ mode, onChange }: { mode: ResearchMode; onChange: (mode: ResearchMode) => void }) {
  return <div className="research-mode-picker">
    <div className="attention-options" role="group" aria-label="Research source period">
      <button type="button" className={`btn btn-small${mode === "replay" ? " selected" : ""}`} aria-pressed={mode === "replay"} onClick={() => onChange("replay")}>Historical demo</button>
      <button type="button" className={`btn btn-small${mode === "live" ? " selected" : ""}`} aria-pressed={mode === "live"} onClick={() => onChange("live")}>Current sources</button>
    </div>
    <p className="fine">{mode === "live" ? "Opening a company reads stored sources. Select Research to explicitly check for current primary documents; dates and source gaps stay visible." : "Research uses documents available by 30 April 2025. The replay is a demonstration, separate from current market data."}</p>
  </div>;
}

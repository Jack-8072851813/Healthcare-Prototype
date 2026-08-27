import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Brain } from 'lucide-react';

interface WhyPanelProps {
  factors: string[];
  score?: number;
  title?: string;
}

const WhyPanel: React.FC<WhyPanelProps> = ({
  factors,
  score,
  title = 'Why this score?',
}) => {
  const [open, setOpen] = useState(false);

  if (!factors || factors.length === 0) return null;

  return (
    <div className="why-panel">
      <button className="why-panel-trigger" onClick={() => setOpen(o => !o)} type="button">
        <Brain size={14} />
        <span>{title}</span>
        {score !== undefined && (
          <span className="why-panel-score">{score}/100</span>
        )}
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {open && (
        <div className="why-panel-body">
          <p className="why-panel-subtitle">Contributing risk factors:</p>
          <ul className="why-panel-list">
            {factors.map((f, i) => (
              <li key={i} className="why-panel-item">
                <span className="why-panel-bullet">⚑</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
          <p className="why-panel-footer">
            Scores are computed using rule-based weighted analysis.
          </p>
        </div>
      )}
    </div>
  );
};

export default WhyPanel;

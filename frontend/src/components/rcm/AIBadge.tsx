import React from 'react';
import { Bot } from 'lucide-react';

interface AIBadgeProps {
  text?: string;
}

const AIBadge: React.FC<AIBadgeProps> = ({ text = 'AI-generated · human review required' }) => (
  <span className="ai-badge" title={text}>
    <Bot size={11} />
    {text}
  </span>
);

export default AIBadge;

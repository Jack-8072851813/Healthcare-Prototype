import React, { useState } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2, Eye, EyeOff } from 'lucide-react';
import type { RadiologyStudy } from '../../data/radiology/studies';

interface XRayViewerProps {
  study?: RadiologyStudy | null;
  uploadedImageUrl?: string | null;
}

const XRayViewer: React.FC<XRayViewerProps> = ({ study, uploadedImageUrl }) => {
  const [zoom, setZoom] = useState(1.0);
  const [showOverlay, setShowOverlay] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.25, 2.5));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.25, 0.75));
  const handleReset = () => {
    setZoom(1.0);
    setShowOverlay(true);
  };

  const isAbnormal = study && study.priority !== 'ROUTINE' && study.priority !== 'PROCESSING';
  const heatmap = study?.heatmapRegion;

  return (
    <div className={`xray-viewer-wrap ${isFullscreen ? 'xray-viewer-fullscreen' : ''}`}>
      {/* Controls Bar */}
      <div className="xray-controls-bar">
        <div className="xray-title">
          <span>Chest X-Ray (PA View)</span>
          <span className="xray-subtitle">{study ? study.id : 'DICOM View'}</span>
        </div>
        <div className="xray-tools">
          <button className="xray-tool-btn" onClick={handleZoomOut} title="Zoom Out" type="button">
            <ZoomOut size={15} />
          </button>
          <span className="xray-zoom-level">{Math.round(zoom * 100)}%</span>
          <button className="xray-tool-btn" onClick={handleZoomIn} title="Zoom In" type="button">
            <ZoomIn size={15} />
          </button>
          <button className="xray-tool-btn" onClick={handleReset} title="Reset View" type="button">
            <RotateCcw size={15} />
          </button>
          {isAbnormal && (
            <button
              className={`xray-tool-btn ${showOverlay ? 'active' : ''}`}
              onClick={() => setShowOverlay(s => !s)}
              title="Toggle AI Overlay"
              type="button"
            >
              {showOverlay ? <Eye size={15} /> : <EyeOff size={15} />}
              <span style={{ fontSize: 11, marginLeft: 4 }}>AI Overlay</span>
            </button>
          )}
          <button
            className="xray-tool-btn"
            onClick={() => setIsFullscreen(f => !f)}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            type="button"
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div className="xray-viewport">
        <div
          className="xray-canvas-container"
          style={{ transform: `scale(${zoom})`, transition: 'transform 0.2s ease-out' }}
        >
          {uploadedImageUrl ? (
            <div className="uploaded-image-preview">
              <img src={uploadedImageUrl} alt="Uploaded Chest X-Ray" />
              {showOverlay && isAbnormal && (
                <div className="simulated-ai-bbox">
                  <span className="bbox-label">{study?.aiFinding} ({study?.confidenceScore}%)</span>
                </div>
              )}
            </div>
          ) : (
            /* Synthetic High-Quality Chest X-Ray SVG Rendering */
            <svg
              viewBox="0 0 400 480"
              className="xray-svg"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <radialGradient id="lungGradientRight" cx="40%" cy="40%" r="60%">
                  <stop offset="0%" stopColor="#0a0c10" />
                  <stop offset="70%" stopColor="#1a202c" />
                  <stop offset="100%" stopColor="#2d3748" />
                </radialGradient>
                <radialGradient id="lungGradientLeft" cx="60%" cy="40%" r="60%">
                  <stop offset="0%" stopColor="#08090d" />
                  <stop offset="70%" stopColor="#181e28" />
                  <stop offset="100%" stopColor="#2d3748" />
                </radialGradient>
                <filter id="blurFilter" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" />
                </filter>
                <radialGradient id="aiHeatmapGrad" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#f97316" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
                </radialGradient>
              </defs>

              {/* Background dark matrix */}
              <rect x="0" y="0" width="400" height="480" fill="#0b0e14" />

              {/* Soft Body Contour */}
              <path
                d="M 60 480 Q 70 120 200 110 Q 330 120 340 480 Z"
                fill="#1f293d"
                opacity="0.3"
              />

              {/* Right Lung Field */}
              <path
                d="M 190 140 C 120 130 90 220 90 360 C 130 380 185 365 190 340 Z"
                fill="url(#lungGradientRight)"
              />

              {/* Left Lung Field */}
              <path
                d="M 210 140 C 280 130 310 220 310 360 C 270 380 215 365 210 340 Z"
                fill="url(#lungGradientLeft)"
              />

              {/* Cardiac Silhouette (Heart Shade) */}
              <path
                d="M 195 240 Q 260 270 240 350 Q 185 365 185 280 Z"
                fill="#3a4a63"
                opacity="0.8"
              />

              {/* Trachea & Spinal Column */}
              <rect x="195" y="60" width="10" height="380" fill="#4a5568" opacity="0.6" rx="3" />
              {Array.from({ length: 14 }).map((_, i) => (
                <rect
                  key={i}
                  x="191"
                  y={120 + i * 22}
                  width="18"
                  height="12"
                  fill="#718096"
                  opacity="0.4"
                  rx="2"
                />
              ))}

              {/* Clavicles */}
              <path
                d="M 70 135 Q 130 155 195 145"
                stroke="#a0aec0"
                strokeWidth="7"
                fill="none"
                strokeLinecap="round"
                opacity="0.75"
              />
              <path
                d="M 330 135 Q 270 155 205 145"
                stroke="#a0aec0"
                strokeWidth="7"
                fill="none"
                strokeLinecap="round"
                opacity="0.75"
              />

              {/* Rib cage shadow arches */}
              {Array.from({ length: 8 }).map((_, i) => (
                <g key={i} opacity="0.4">
                  <path
                    d={`M 192 ${160 + i * 26} C 130 ${170 + i * 26} 95 ${200 + i * 26} 95 ${215 + i * 26}`}
                    stroke="#cbd5e0"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    d={`M 208 ${160 + i * 26} C 270 ${170 + i * 26} 305 ${200 + i * 26} 305 ${215 + i * 26}`}
                    stroke="#cbd5e0"
                    strokeWidth="4"
                    fill="none"
                  />
                </g>
              ))}

              {/* Diaphragm Curves */}
              <path
                d="M 80 375 Q 140 345 195 365"
                stroke="#a0aec0"
                strokeWidth="4"
                fill="none"
                opacity="0.8"
              />
              <path
                d="M 320 375 Q 260 345 205 365"
                stroke="#a0aec0"
                strokeWidth="4"
                fill="none"
                opacity="0.8"
              />

              {/* Simulated Abnormality Highlight Overlay */}
              {showOverlay && isAbnormal && heatmap && (
                <g className="ai-heatmap-layer">
                  <circle
                    cx={heatmap.x * 4}
                    cy={heatmap.y * 4.5}
                    r={heatmap.radius * 2}
                    fill="url(#aiHeatmapGrad)"
                    filter="url(#blurFilter)"
                  />
                  <rect
                    x={heatmap.x * 4 - heatmap.radius * 2}
                    y={heatmap.y * 4.5 - heatmap.radius * 2}
                    width={heatmap.radius * 4}
                    height={heatmap.radius * 4}
                    fill="none"
                    stroke={study?.priority === 'CRITICAL' ? '#ef4444' : '#f97316'}
                    strokeWidth="2"
                    strokeDasharray="4 3"
                    rx="6"
                  />
                  <text
                    x={heatmap.x * 4 - heatmap.radius * 2}
                    y={heatmap.y * 4.5 - heatmap.radius * 2 - 8}
                    fill={study?.priority === 'CRITICAL' ? '#fca5a5' : '#fed7aa'}
                    fontSize="11"
                    fontWeight="700"
                    fontFamily="sans-serif"
                  >
                    AI FLAG: {study?.aiFinding} ({study?.confidenceScore}%)
                  </text>
                </g>
              )}

              {/* Medical Image Orientations */}
              <text x="18" y="30" fill="#718096" fontSize="14" fontWeight="700">R</text>
              <text x="370" y="30" fill="#718096" fontSize="14" fontWeight="700">L</text>
              <text x="18" y="460" fill="#4a5568" fontSize="10">DICOM / CHEST PA</text>
            </svg>
          )}
        </div>
      </div>

      {/* Image Footer info */}
      <div className="xray-footer-info">
        <span>Modality: <strong>{study?.modality || 'CR'}</strong></span>
        <span>View: <strong>CHEST PA</strong></span>
        <span>Window/Level: <strong>STANDARD CHEST</strong></span>
        {isAbnormal && showOverlay && (
          <span className="xray-flag-indicator">
            ⚑ AI Detected Anomaly Region Active
          </span>
        )}
      </div>
    </div>
  );
};

export default XRayViewer;

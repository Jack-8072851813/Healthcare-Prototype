import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database, Cpu, Layers, Sparkles, CheckCircle2,
  FileCheck, Shield, HardDrive, ArrowDown, ExternalLink,
} from 'lucide-react';
import AIBadge from '../../../components/rcm/AIBadge';

interface PipelineStage {
  id: string;
  name: string;
  subtitle: string;
  layer: 'Raw' | 'Bronze' | 'Silver' | 'Model' | 'Gold' | 'UI';
  icon: React.ReactNode;
  color: string;
  description: string;
  technicalDetails: string[];
}

const STAGES: PipelineStage[] = [
  {
    id: 'stage-1',
    name: 'DICOM Chest X-Ray Ingestion',
    subtitle: 'Hospital Imaging Stream',
    layer: 'Raw',
    icon: <HardDrive size={22} />,
    color: '#4A90D9',
    description: 'Digital Radiography (CR/DX) images arrive in DICOM standard format containing high-resolution 16-bit pixel matrices and patient metadata headers.',
    technicalDetails: [
      'De-identification pipeline removes personal health information (PHI)',
      'Validates DICOM SOP Class UID for Chest Radiographs',
      'Supports batch and near-real-time arrival streams',
    ],
  },
  {
    id: 'stage-2',
    name: 'Databricks Unity Catalog Volume',
    subtitle: 'Secure Cloud Object Storage',
    layer: 'Raw',
    icon: <Database size={22} />,
    color: '#5AAFA5',
    description: 'Centralized, governed storage location within Databricks Unity Catalog for binary DICOM file objects with fine-grained access control.',
    technicalDetails: [
      'Unity Catalog volumes ensure strict audit logging & governance',
      'Encrypted at rest with hospital enterprise keys',
      'Unified data cataloging across engineering and data science teams',
    ],
  },
  {
    id: 'stage-3',
    name: 'Bronze Layer — Raw Metadata Table',
    subtitle: 'Delta Lake Storage',
    layer: 'Bronze',
    icon: <Layers size={22} />,
    color: '#805AD5',
    description: 'Extracted DICOM header attributes (Study ID, Modality, Body Part, Study Time, Pixel Dimensions) stored as structured Delta Lake tables.',
    technicalDetails: [
      'ACID transaction guarantees with Delta Lake schema enforcement',
      'Preserves original raw metadata for auditability',
      'Triggers automated pipeline downstream on new row insert',
    ],
  },
  {
    id: 'stage-4',
    name: 'Image Validation & Preprocessing',
    subtitle: 'PyTorch / OpenCV Engine',
    layer: 'Silver',
    icon: <Cpu size={22} />,
    color: '#DD6B20',
    description: 'DICOM pixel array extraction, windowing/leveling (bone/lung window presets), resizing to 512x512, histogram normalization, and contrast enhancement.',
    technicalDetails: [
      'Converts 16-bit DICOM pixel arrays to standardized float tensors',
      'Applies CLAHE (Contrast Limited Adaptive Histogram Equalization)',
      'Filters unreadable or artifact-corrupted scans before model scoring',
    ],
  },
  {
    id: 'stage-5',
    name: 'Silver Layer — AI-Ready Dataset',
    subtitle: 'Normalized Tensor Table',
    layer: 'Silver',
    icon: <FileCheck size={22} />,
    color: '#319795',
    description: 'Preprocessed, validated images and standardized tensor structures ready for batch GPU inference scoring.',
    technicalDetails: [
      'Optimized Parquet/Delta format for GPU memory loading',
      'Cross-validated with quality assurance rules',
      'Indexed by Study ID for rapid feature lookup',
    ],
  },
  {
    id: 'stage-6',
    name: 'Deep Learning Model & MLflow Tracking',
    subtitle: 'DenseNet-121 / ResNet50 Classifier',
    layer: 'Model',
    icon: <Sparkles size={22} />,
    color: '#D69E2E',
    description: 'Convolutional Neural Network trained on large chest radiograph datasets to predict abnormality probabilities for Pneumothorax, Pneumonia, and Pleural Effusion.',
    technicalDetails: [
      'Registered in MLflow Model Registry with versioning (`chest-xray-triage-v1`)',
      'Generates class probabilities + spatial Grad-CAM activation maps',
      'Automated model lineage tracking and metrics reporting',
    ],
  },
  {
    id: 'stage-7',
    name: 'Triage Rules Engine',
    subtitle: 'Clinical Priority Classification',
    layer: 'Gold',
    icon: <Shield size={22} />,
    color: '#E53E3E',
    description: 'Evaluates probability outputs against threshold rules to assign clinical triage priority: CRITICAL (Pneumothorax > 90%), HIGH (Pneumonia/Effusion > 75%), or ROUTINE.',
    technicalDetails: [
      'Configurable probability cutoff thresholds per abnormality',
      'Integrates waiting time decay factors for routine queue escalation',
      'Flags urgent critical cases for immediate push notifications',
    ],
  },
  {
    id: 'stage-8',
    name: 'Gold Layer — Triage Results Table',
    subtitle: 'Serving Ready Delta Table',
    layer: 'Gold',
    icon: <CheckCircle2 size={22} />,
    color: '#38A169',
    description: 'Final prioritized worklist table containing Study IDs, Findings, Confidence Scores, Triage Priorities, and Radiologist Review status.',
    technicalDetails: [
      'Low-latency serving table optimized for dashboard REST API queries',
      'Immutable audit log of all AI predictions and radiologist feedback',
      'Feeds model performance monitoring metrics pipelines',
    ],
  },
  {
    id: 'stage-9',
    name: 'Radiology Triage Dashboard',
    subtitle: 'Meridian Frontend UI',
    layer: 'UI',
    icon: <Layers size={22} />,
    color: '#3182CE',
    description: 'Interactive clinical decision-support interface presenting the prioritized worklist to radiologists for expedited review of urgent studies.',
    technicalDetails: [
      'REST API abstraction layers for seamless Databricks connection',
      'Interactive DICOM image viewer with heatmap overlays',
      'Captures radiologist feedback for continuous learning',
    ],
  },
];

const DatabricksPipeline: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2>Databricks AI Pipeline Architecture</h2>
            <AIBadge text="Unity Catalog & Delta Lake Medallion Architecture" />
          </div>
          <p>End-to-End Data & Model Pipeline for Chest X-Ray Triage</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} type="button">
          ← Back to Worklist
        </button>
      </div>

      {/* Visual Pipeline Flowchart Diagram per Requirement 12 */}
      <div className="chart-card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3>Medallion Data Flow (Bronze → Silver → Gold)</h3>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Databricks Managed Pipeline</span>
        </div>
        <div className="card-body">
          <div className="pipeline-flow-container" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {STAGES.map((stage, idx) => (
              <React.Fragment key={stage.id}>
                <div
                  className="pipeline-stage-card"
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 16,
                    padding: 16,
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    borderLeft: `5px solid ${stage.color}`,
                    background: '#fff',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.03)',
                  }}
                >
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 8,
                      background: `${stage.color}15`,
                      color: stage.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {stage.icon}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>{stage.name}</h4>
                      <span className="category-tag" style={{ background: `${stage.color}20`, color: stage.color }}>
                        {stage.layer}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{stage.subtitle}</span>
                    </div>

                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '6px 0 10px', lineHeight: 1.5 }}>
                      {stage.description}
                    </p>

                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      {stage.technicalDetails.map((detail, dIdx) => (
                        <span key={dIdx} style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ color: stage.color }}>▸</span> {detail}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {idx < STAGES.length - 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', margin: '-4px 0' }}>
                    <ArrowDown size={20} style={{ color: 'var(--text-muted)', opacity: 0.6 }} />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DatabricksPipeline;
